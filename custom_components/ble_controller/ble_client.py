"""BLE GATT 클라이언트 헬퍼."""

from __future__ import annotations

import asyncio
import logging

from bleak import BleakClient
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


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
    ble_device = async_ble_device_from_address(hass, mac, connectable=True)
    if ble_device is None:
        _LOGGER.warning("BLE 디바이스를 찾을 수 없음: %s", mac)
        return False

    try:
        client = await establish_connection(BleakClient, ble_device, mac)
    except Exception:
        _LOGGER.exception("BLE 연결 실패: %s", mac)
        return False

    try:
        await client.write_gatt_char(char_uuid, data, response=response)
        return True
    except Exception:
        _LOGGER.exception("GATT write 실패: %s", mac)
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            _LOGGER.debug("연결 해제 실패 (무시): %s", mac)


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
    ble_device = async_ble_device_from_address(hass, mac, connectable=True)
    if ble_device is None:
        _LOGGER.warning("BLE 디바이스를 찾을 수 없음: %s", mac)
        return False, None

    try:
        client = await establish_connection(BleakClient, ble_device, mac)
    except Exception:
        _LOGGER.exception("BLE 연결 실패: %s", mac)
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
        try:
            await client.disconnect()
        except Exception:
            _LOGGER.debug("연결 해제 실패 (무시): %s", mac)
