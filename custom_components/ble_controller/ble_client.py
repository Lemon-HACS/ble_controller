"""BLE GATT 클라이언트 — persistent connection + keepalive 패턴.

SwitchBot / LED BLE 통합과 동일한 아키텍처:
  - 첫 커맨드에서 연결, 일정 시간 미사용 시 자동 해제
  - keep_alive 모드: 백그라운드에서 미리 연결 + 주기적 재연결
  - asyncio.Lock으로 연결/명령 직렬화
  - establish_connection + BleakClientWithServiceCache 사용
  - persistent notify: 연결 시 1회 구독, 연결 유지되는 동안 유지
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

from bleak_retry_connector import (
    BleakClientWithServiceCache,
    close_stale_connections_by_address,
    establish_connection,
)

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DISCONNECT_DELAY = 15.0  # 마지막 명령 후 자동 해제까지 대기 시간
KEEPALIVE_INTERVAL = 10.0  # keepalive 체크 + ping 주기
GATT_TIMEOUT = 3.0  # GATT 오퍼레이션(write 등) 최대 대기 시간
MAX_ATTEMPTS = 3


class BLEDeviceManager:
    """디바이스별 BLE 연결 매니저.

    연결을 유지하다가 DISCONNECT_DELAY 동안 미사용 시 자동 해제.
    """

    def __init__(
        self, hass: HomeAssistant, mac: str, *,
        keep_alive: bool = False, keepalive_interval: int = 10,
    ) -> None:
        self._hass = hass
        self._mac = mac
        self._keep_alive = keep_alive
        self._keepalive_interval = keepalive_interval
        self._client: BleakClientWithServiceCache | None = None
        self._connect_lock = asyncio.Lock()
        self._operation_lock = asyncio.Lock()
        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._keepalive_task: asyncio.Task | None = None
        self._on_connect_callback: Callable[[], Coroutine] | None = None
        self._expected_disconnect = False

        # Persistent notify subscription
        self._persistent_notify_uuid: str | None = None
        self._notify_subscribed = False
        self._notify_event = asyncio.Event()
        self._notify_data_buffer: list[bytes] = []

    def _get_ble_device(self):
        """최신 BLEDevice 참조 반환."""
        return async_ble_device_from_address(self._hass, self._mac, connectable=True)

    def setup_persistent_notify(self, notify_uuid: str) -> None:
        """Persistent notify 구독 설정. 연결 시 자동 구독, 해제 시 자동 해지."""
        self._persistent_notify_uuid = notify_uuid

    def _on_disconnected(self, _client: Any) -> None:
        """BlueZ에서 연결이 끊겼을 때 콜백."""
        if self._expected_disconnect:
            _LOGGER.debug("[BLE %s] 예상된 연결 해제", self._mac)
        else:
            _LOGGER.warning("[BLE %s] 예기치 않은 연결 끊김", self._mac)
        self._client = None
        self._notify_subscribed = False
        self._cancel_disconnect_timer()

    def _cancel_disconnect_timer(self) -> None:
        if self._disconnect_timer is not None:
            self._disconnect_timer.cancel()
            self._disconnect_timer = None

    def _reset_disconnect_timer(self) -> None:
        if self._keep_alive:
            return
        self._cancel_disconnect_timer()
        loop = self._hass.loop
        self._disconnect_timer = loop.call_later(
            DISCONNECT_DELAY,
            lambda: asyncio.ensure_future(self._timed_disconnect()),
        )

    async def _timed_disconnect(self) -> None:
        """타이머에 의한 자동 연결 해제."""
        _LOGGER.debug("[BLE %s] 타이머 만료 — 연결 해제", self._mac)
        await self._disconnect()

    # ── Persistent Notify ──────────────────────────────────────────

    def _on_notify(self, _handle: int, data: bytearray) -> None:
        """Persistent notify 수신 콜백."""
        raw = bytes(data)
        _LOGGER.debug("[BLE %s] Notify: %s", self._mac, raw.hex())
        self._notify_data_buffer.append(raw)
        self._notify_event.set()

    async def _subscribe_persistent_notify(self) -> None:
        """연결 직후 persistent notify 구독."""
        if not self._persistent_notify_uuid or self._notify_subscribed:
            return
        if self._client is None or not self._client.is_connected:
            return
        try:
            await self._client.start_notify(
                self._persistent_notify_uuid, self._on_notify
            )
            self._notify_subscribed = True
            _LOGGER.info("[BLE %s] Persistent notify 구독 완료: %s",
                         self._mac, self._persistent_notify_uuid)
        except Exception:
            _LOGGER.exception("[BLE %s] Persistent notify 구독 실패", self._mac)

    def _clear_notify_buffer(self) -> None:
        """Notify 버퍼 초기화."""
        self._notify_data_buffer.clear()
        self._notify_event.clear()

    async def _wait_for_notify_match(
        self,
        on_pattern: bytes | None,
        off_pattern: bytes | None,
        timeout: float,
    ) -> bool | None:
        """Notify 버퍼에서 ON/OFF 패턴 매칭. 타임아웃까지 대기.

        여러 notify 응답이 올 수 있으므로 버퍼의 모든 항목을 검사.
        """
        if not self._notify_subscribed:
            return None

        deadline = time.monotonic() + timeout
        while True:
            for raw in self._notify_data_buffer:
                if on_pattern and on_pattern in raw:
                    return True
                if off_pattern and off_pattern in raw:
                    return False

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None

            self._notify_event.clear()
            try:
                await asyncio.wait_for(
                    self._notify_event.wait(), timeout=remaining
                )
            except TimeoutError:
                # 마지막으로 한번 더 버퍼 체크
                for raw in self._notify_data_buffer:
                    if on_pattern and on_pattern in raw:
                        return True
                    if off_pattern and off_pattern in raw:
                        return False
                return None

    # ── Connection ─────────────────────────────────────────────────

    async def _ensure_connected(self) -> bool:
        """연결이 없으면 새로 연결. 성공 시 True."""
        async with self._connect_lock:
            if self._client is not None and self._client.is_connected:
                _LOGGER.debug("[BLE %s] 기존 연결 재사용", self._mac)
                self._reset_disconnect_timer()
                return True

            self._client = None
            self._notify_subscribed = False
            ble_device = self._get_ble_device()
            if ble_device is None:
                _LOGGER.warning("[BLE %s] 디바이스를 찾을 수 없음", self._mac)
                return False

            _LOGGER.debug(
                "[BLE %s] 디바이스 발견: name=%s, rssi=%s",
                self._mac,
                getattr(ble_device, "name", "?"),
                getattr(ble_device, "rssi", "?"),
            )

            t_start = time.monotonic()
            _LOGGER.info("[BLE %s] 연결 시도 (max_attempts=%d)", self._mac, MAX_ATTEMPTS)

            self._expected_disconnect = False
            try:
                self._client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    self._mac,
                    self._on_disconnected,
                    max_attempts=MAX_ATTEMPTS,
                    ble_device_callback=self._get_ble_device,
                )
            except Exception as err:
                elapsed = time.monotonic() - t_start
                _LOGGER.warning(
                    "[BLE %s] 연결 실패 (%.1f초): %s: %s",
                    self._mac,
                    elapsed,
                    type(err).__name__,
                    err,
                )
                return False

            elapsed = time.monotonic() - t_start
            _LOGGER.info("[BLE %s] 연결 성공 (%.1f초)", self._mac, elapsed)
            self._reset_disconnect_timer()

            # 연결 직후 persistent notify 구독
            await self._subscribe_persistent_notify()
            return True

    async def _disconnect(self) -> None:
        """안전하게 연결 해제."""
        async with self._connect_lock:
            self._cancel_disconnect_timer()
            client = self._client
            self._client = None
            self._notify_subscribed = False
            if client is None:
                return
            self._expected_disconnect = True
            try:
                await client.disconnect()
            except Exception:
                _LOGGER.debug("[BLE %s] 연결 해제 실패 (무시)", self._mac)

    # ── Keepalive ──────────────────────────────────────────────────

    def set_on_connect_callback(
        self, callback: Callable[[], Coroutine] | None
    ) -> None:
        """연결 성공 시 호출할 콜백 등록 (예: 초기 상태 조회)."""
        self._on_connect_callback = callback

    def start_keepalive(self) -> None:
        """keep_alive 모드일 때 백그라운드 연결 + keepalive 루프 시작."""
        if self._keep_alive and self._keepalive_task is None:
            self._keepalive_task = asyncio.ensure_future(self._keepalive_loop())

    async def _keepalive_loop(self) -> None:
        """백그라운드 keepalive 루프: 즉시 연결 후 주기적으로 ping + 재연결."""
        try:
            _LOGGER.info("[BLE %s] Keepalive 시작 — 초기 연결 시도", self._mac)
            if await self._ensure_connected():
                await self._fire_on_connect()
            while True:
                await asyncio.sleep(self._keepalive_interval)
                if self._client is None or not self._client.is_connected:
                    _LOGGER.info("[BLE %s] Keepalive: 연결 끊김 감지 — 재연결", self._mac)
                    if await self._ensure_connected():
                        await self._fire_on_connect()
                else:
                    # 연결 유지 중 — ping으로 연결 살리기 + 상태 갱신
                    _LOGGER.debug("[BLE %s] Keepalive: ping (상태 조회)", self._mac)
                    await self._fire_on_connect()
        except asyncio.CancelledError:
            _LOGGER.debug("[BLE %s] Keepalive 루프 종료", self._mac)

    async def _fire_on_connect(self) -> None:
        """on_connect 콜백 실행."""
        if self._on_connect_callback is not None:
            try:
                await self._on_connect_callback()
            except Exception:
                _LOGGER.exception("[BLE %s] on_connect 콜백 실패", self._mac)

    # ── Operations ─────────────────────────────────────────────────

    async def query_status(
        self,
        char_uuid: str,
        data: bytes,
        notify_on_pattern: bytes | None = None,
        notify_off_pattern: bytes | None = None,
        notify_timeout: float = 3.0,
    ) -> bool | None:
        """상태 조회 커맨드 전송 후 persistent notify로 ON/OFF 판별.

        _operation_lock을 잡지 않음 — keepalive 콜백에서 호출되므로
        사용자의 write 명령을 차단하지 않기 위함.

        Returns:
            True=ON, False=OFF, None=판별 불가.
        """
        if self._client is None or not self._client.is_connected:
            _LOGGER.warning("[BLE %s] query_status: 연결 안 됨", self._mac)
            return None
        if not self._notify_subscribed:
            _LOGGER.warning("[BLE %s] query_status: notify 미구독", self._mac)
            return None

        _LOGGER.info(
            "[BLE %s] query_status: char=%s, data=%s",
            self._mac, char_uuid, data.hex(),
        )
        try:
            self._clear_notify_buffer()
            await asyncio.wait_for(
                self._client.write_gatt_char(char_uuid, data, response=False),
                timeout=GATT_TIMEOUT,
            )
            state = await self._wait_for_notify_match(
                notify_on_pattern, notify_off_pattern, notify_timeout
            )
            _LOGGER.info("[BLE %s] query_status 결과: %s", self._mac, state)
            return state
        except TimeoutError:
            _LOGGER.error("[BLE %s] query_status: GATT write 타임아웃 — 연결 끊김 의심", self._mac)
            await self._disconnect()
            return None
        except Exception:
            _LOGGER.exception("[BLE %s] query_status 실패", self._mac)
            return None

    async def async_shutdown(self) -> None:
        """통합 언로드 시 정리."""
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            self._keepalive_task = None
        await self._disconnect()
        try:
            await close_stale_connections_by_address(self._mac)
        except Exception:
            pass

    async def write(
        self,
        char_uuid: str,
        data: bytes,
        response: bool = False,
    ) -> bool:
        """GATT write. 성공 시 True."""
        _LOGGER.info(
            "[BLE %s] write: char=%s, data=%s, response=%s",
            self._mac, char_uuid, data.hex(), response,
        )
        async with self._operation_lock:
            if not await self._ensure_connected():
                _LOGGER.error("[BLE %s] write: 연결 실패로 중단", self._mac)
                return False
            try:
                await asyncio.wait_for(
                    self._client.write_gatt_char(char_uuid, data, response=response),
                    timeout=GATT_TIMEOUT,
                )
                _LOGGER.info("[BLE %s] write: 성공", self._mac)
                self._reset_disconnect_timer()
                return True
            except TimeoutError:
                _LOGGER.error("[BLE %s] write: GATT write 타임아웃 — 강제 disconnect", self._mac)
                await self._disconnect()
                return False
            except Exception:
                _LOGGER.exception("[BLE %s] GATT write 실패", self._mac)
                await self._disconnect()
                return False

    async def write_and_notify(
        self,
        char_uuid: str,
        data: bytes,
        response: bool = False,
        notify_on_pattern: bytes | None = None,
        notify_off_pattern: bytes | None = None,
        notify_timeout: float = 1.5,
    ) -> tuple[bool, bool | None]:
        """GATT write 후 persistent notify에서 상태 확인.

        Persistent notify가 구독되어 있으면 start/stop 없이 바로 대기.
        없으면 plain write와 동일.

        Returns:
            (성공 여부, 감지된 상태) — 판별 불가 시 None.
        """
        _LOGGER.info(
            "[BLE %s] write_and_notify: char=%s, data=%s",
            self._mac, char_uuid, data.hex(),
        )
        async with self._operation_lock:
            if not await self._ensure_connected():
                _LOGGER.error("[BLE %s] write_and_notify: 연결 실패로 중단", self._mac)
                return False, None

            try:
                self._clear_notify_buffer()
                await asyncio.wait_for(
                    self._client.write_gatt_char(
                        char_uuid, data, response=response
                    ),
                    timeout=GATT_TIMEOUT,
                )

                detected_state: bool | None = None
                if self._notify_subscribed and (notify_on_pattern or notify_off_pattern):
                    detected_state = await self._wait_for_notify_match(
                        notify_on_pattern, notify_off_pattern, notify_timeout
                    )

                _LOGGER.info("[BLE %s] write_and_notify: 성공 (state=%s)",
                             self._mac, detected_state)
                self._reset_disconnect_timer()
                return True, detected_state
            except TimeoutError:
                _LOGGER.error("[BLE %s] write_and_notify: GATT write 타임아웃 — 강제 disconnect", self._mac)
                await self._disconnect()
                return False, None
            except Exception:
                _LOGGER.exception("[BLE %s] GATT write 실패", self._mac)
                await self._disconnect()
                return False, None
