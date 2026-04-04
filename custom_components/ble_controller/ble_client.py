"""BLE GATT 클라이언트 헬퍼."""

from __future__ import annotations

import asyncio
import logging
import time

from bleak import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakConnectionError,
    BleakNotFoundError,
    establish_connection,
)

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

MAX_ATTEMPTS = 6
CONNECT_TIMEOUT = 30.0
RETRY_DELAY = 2.0
MAX_RETRIES = 5


async def _get_client(
    hass: HomeAssistant, mac: str
) -> BleakClientWithServiceCache | None:
    """BLE 디바이스를 찾아 연결된 BleakClient 반환.

    InProgress / 연결 실패 시 대기 후 재시도.
    """
    t_start = time.monotonic()
    _LOGGER.info("[BLE %s] 연결 시작", mac)

    ble_device = async_ble_device_from_address(hass, mac, connectable=True)
    if ble_device is None:
        _LOGGER.warning("[BLE %s] 디바이스를 찾을 수 없음 (advertising 미감지)", mac)
        return None

    _LOGGER.debug(
        "[BLE %s] 디바이스 발견: name=%s, rssi=%s",
        mac,
        getattr(ble_device, "name", "?"),
        getattr(ble_device, "rssi", "?"),
    )

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        t_attempt = time.monotonic()
        _LOGGER.info(
            "[BLE %s] establish_connection 시도 %d/%d (max_attempts=%d, timeout=%.0fs)",
            mac,
            attempt + 1,
            MAX_RETRIES,
            MAX_ATTEMPTS,
            CONNECT_TIMEOUT,
        )
        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                mac,
                max_attempts=MAX_ATTEMPTS,
                timeout=CONNECT_TIMEOUT,
            )
            elapsed = time.monotonic() - t_start
            _LOGGER.info(
                "[BLE %s] 연결 성공 (시도 %d, 총 %.1f초)",
                mac,
                attempt + 1,
                elapsed,
            )
            return client
        except (BleakNotFoundError, BleakConnectionError, BleakError) as err:
            last_error = err
            attempt_elapsed = time.monotonic() - t_attempt
            _LOGGER.warning(
                "[BLE %s] 연결 실패 (%d/%d, %.1f초): %s: %s",
                mac,
                attempt + 1,
                MAX_RETRIES,
                attempt_elapsed,
                type(err).__name__,
                err,
            )
            await asyncio.sleep(RETRY_DELAY)
            # 디바이스 정보 갱신
            ble_device = async_ble_device_from_address(
                hass, mac, connectable=True
            )
            if ble_device is None:
                _LOGGER.warning(
                    "[BLE %s] 재시도 중 디바이스 사라짐", mac
                )
                return None
        except Exception:
            _LOGGER.exception("[BLE %s] 예상 외 에러", mac)
            return None

    total_elapsed = time.monotonic() - t_start
    _LOGGER.error(
        "[BLE %s] 연결 포기 (%d회 재시도, 총 %.1f초): %s",
        mac,
        MAX_RETRIES,
        total_elapsed,
        last_error,
    )
    return None


async def _disconnect(
    client: BleakClientWithServiceCache, mac: str
) -> None:
    """안전하게 연결 해제."""
    try:
        await client.disconnect()
    except Exception:
        _LOGGER.debug("연결 해제 실패 (무시): %s", mac)


async def ble_write(
    hass: HomeAssistant,
    mac: str,
    char_uuid: str,
    data: bytes,
    response: bool = False,
) -> bool:
    """BLE 디바이스에 연결하여 GATT write 후 연결 해제.

    성공 시 True, 실패 시 False 반환.
    """
    _LOGGER.info(
        "[BLE %s] ble_write: char=%s, data=%s, response=%s",
        mac,
        char_uuid,
        data.hex(),
        response,
    )
    client = await _get_client(hass, mac)
    if client is None:
        _LOGGER.error("[BLE %s] ble_write: 연결 실패로 중단", mac)
        return False

    try:
        await client.write_gatt_char(char_uuid, data, response=response)
        _LOGGER.info("[BLE %s] ble_write: 성공", mac)
        return True
    except Exception:
        _LOGGER.exception("[BLE %s] GATT write 실패", mac)
        return False
    finally:
        await _disconnect(client, mac)


async def ble_write_and_notify(
    hass: HomeAssistant,
    mac: str,
    char_uuid: str,
    data: bytes,
    response: bool = False,
    notify_uuid: str | None = None,
    notify_on_pattern: bytes | None = None,
    notify_off_pattern: bytes | None = None,
    notify_timeout: float = 5.0,
) -> tuple[bool, bool | None]:
    """BLE write 후 Notify로 상태 확인.

    Returns:
        (성공 여부, 감지된 상태) — 상태를 판별할 수 없으면 None.
    """
    _LOGGER.info(
        "[BLE %s] ble_write_and_notify: char=%s, data=%s, notify_uuid=%s",
        mac,
        char_uuid,
        data.hex(),
        notify_uuid,
    )
    client = await _get_client(hass, mac)
    if client is None:
        _LOGGER.error("[BLE %s] ble_write_and_notify: 연결 실패로 중단", mac)
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

            await client.start_notify(notify_uuid, on_notify)
            await client.write_gatt_char(char_uuid, data, response=response)
            try:
                await asyncio.wait_for(state_event.wait(), timeout=notify_timeout)
            except TimeoutError:
                _LOGGER.debug("Notify 타임아웃: %s (상태 미확인)", mac)
            await client.stop_notify(notify_uuid)
        else:
            await client.write_gatt_char(char_uuid, data, response=response)

        return True, detected_state
    except Exception:
        _LOGGER.exception("GATT write 실패: %s", mac)
        return False, None
    finally:
        await _disconnect(client, mac)
