"""BLE GATT 클라이언트 — persistent connection + keepalive 패턴.

SwitchBot / LED BLE 통합과 동일한 아키텍처:
  - 첫 커맨드에서 연결, 일정 시간 미사용 시 자동 해제
  - keep_alive 모드: 백그라운드에서 미리 연결 + 주기적 재연결
  - asyncio.Lock으로 연결/명령 직렬화
  - establish_connection + BleakClientWithServiceCache 사용
"""

from __future__ import annotations

import asyncio
import logging
import time
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
KEEPALIVE_INTERVAL = 60.0  # keepalive 체크 주기
MAX_ATTEMPTS = 3


class BLEDeviceManager:
    """디바이스별 BLE 연결 매니저.

    연결을 유지하다가 DISCONNECT_DELAY 동안 미사용 시 자동 해제.
    """

    def __init__(
        self, hass: HomeAssistant, mac: str, *, keep_alive: bool = False
    ) -> None:
        self._hass = hass
        self._mac = mac
        self._keep_alive = keep_alive
        self._client: BleakClientWithServiceCache | None = None
        self._connect_lock = asyncio.Lock()
        self._operation_lock = asyncio.Lock()
        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._keepalive_task: asyncio.Task | None = None
        self._expected_disconnect = False

    def _get_ble_device(self):
        """최신 BLEDevice 참조 반환."""
        return async_ble_device_from_address(self._hass, self._mac, connectable=True)

    def _on_disconnected(self, _client: Any) -> None:
        """BlueZ에서 연결이 끊겼을 때 콜백."""
        if self._expected_disconnect:
            _LOGGER.debug("[BLE %s] 예상된 연결 해제", self._mac)
        else:
            _LOGGER.warning("[BLE %s] 예기치 않은 연결 끊김", self._mac)
        self._client = None
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

    async def _ensure_connected(self) -> bool:
        """연결이 없으면 새로 연결. 성공 시 True."""
        async with self._connect_lock:
            if self._client is not None and self._client.is_connected:
                _LOGGER.debug("[BLE %s] 기존 연결 재사용", self._mac)
                self._reset_disconnect_timer()
                return True

            self._client = None
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
            return True

    async def _disconnect(self) -> None:
        """안전하게 연결 해제."""
        async with self._connect_lock:
            self._cancel_disconnect_timer()
            client = self._client
            self._client = None
            if client is None:
                return
            self._expected_disconnect = True
            try:
                await client.disconnect()
            except Exception:
                _LOGGER.debug("[BLE %s] 연결 해제 실패 (무시)", self._mac)

    def start_keepalive(self) -> None:
        """keep_alive 모드일 때 백그라운드 연결 + keepalive 루프 시작."""
        if self._keep_alive and self._keepalive_task is None:
            self._keepalive_task = asyncio.ensure_future(self._keepalive_loop())

    async def _keepalive_loop(self) -> None:
        """백그라운드 keepalive 루프: 즉시 연결 후 주기적으로 상태 체크 + 재연결."""
        try:
            _LOGGER.info("[BLE %s] Keepalive 시작 — 초기 연결 시도", self._mac)
            await self._ensure_connected()
            while True:
                await asyncio.sleep(KEEPALIVE_INTERVAL)
                if self._client is None or not self._client.is_connected:
                    _LOGGER.info("[BLE %s] Keepalive: 연결 끊김 감지 — 재연결", self._mac)
                    await self._ensure_connected()
                else:
                    _LOGGER.debug("[BLE %s] Keepalive: 연결 유지 중", self._mac)
        except asyncio.CancelledError:
            _LOGGER.debug("[BLE %s] Keepalive 루프 종료", self._mac)

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
            self._mac,
            char_uuid,
            data.hex(),
            response,
        )
        async with self._operation_lock:
            if not await self._ensure_connected():
                _LOGGER.error("[BLE %s] write: 연결 실패로 중단", self._mac)
                return False
            try:
                await self._client.write_gatt_char(char_uuid, data, response=response)
                _LOGGER.info("[BLE %s] write: 성공", self._mac)
                self._reset_disconnect_timer()
                return True
            except Exception:
                _LOGGER.exception("[BLE %s] GATT write 실패", self._mac)
                await self._disconnect()
                return False

    async def write_and_notify(
        self,
        char_uuid: str,
        data: bytes,
        response: bool = False,
        notify_uuid: str | None = None,
        notify_on_pattern: bytes | None = None,
        notify_off_pattern: bytes | None = None,
        notify_timeout: float = 5.0,
    ) -> tuple[bool, bool | None]:
        """GATT write 후 Notify로 상태 확인.

        Returns:
            (성공 여부, 감지된 상태) — 판별 불가 시 None.
        """
        _LOGGER.info(
            "[BLE %s] write_and_notify: char=%s, data=%s, notify=%s",
            self._mac,
            char_uuid,
            data.hex(),
            notify_uuid,
        )
        async with self._operation_lock:
            if not await self._ensure_connected():
                _LOGGER.error("[BLE %s] write_and_notify: 연결 실패로 중단", self._mac)
                return False, None

            detected_state: bool | None = None

            try:
                if notify_uuid and (notify_on_pattern or notify_off_pattern):
                    state_event = asyncio.Event()

                    def on_notify(_handle: int, notify_data: bytearray) -> None:
                        nonlocal detected_state
                        raw = bytes(notify_data)
                        if notify_on_pattern and notify_on_pattern in raw:
                            detected_state = True
                            state_event.set()
                        elif notify_off_pattern and notify_off_pattern in raw:
                            detected_state = False
                            state_event.set()

                    await self._client.start_notify(notify_uuid, on_notify)
                    await self._client.write_gatt_char(
                        char_uuid, data, response=response
                    )
                    try:
                        await asyncio.wait_for(
                            state_event.wait(), timeout=notify_timeout
                        )
                    except TimeoutError:
                        _LOGGER.debug("[BLE %s] Notify 타임아웃 (상태 미확인)", self._mac)
                    await self._client.stop_notify(notify_uuid)
                else:
                    await self._client.write_gatt_char(
                        char_uuid, data, response=response
                    )

                _LOGGER.info("[BLE %s] write_and_notify: 성공", self._mac)
                self._reset_disconnect_timer()
                return True, detected_state
            except Exception:
                _LOGGER.exception("[BLE %s] GATT write 실패", self._mac)
                await self._disconnect()
                return False, None
