"""BLE Controller 스위치 플랫폼."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble_client import BLEDeviceManager
from .const import (
    CONF_CHAR_UUID,
    CONF_DATA_OFF,
    CONF_DATA_ON,
    CONF_KEEP_ALIVE,
    CONF_NOTIFY_OFF_PATTERN,
    CONF_NOTIFY_ON_PATTERN,
    CONF_NOTIFY_UUID,
    CONF_STATUS_QUERY_DATA,
    CONF_WRITE_WITH_RESPONSE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """스위치 엔티티 셋업."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    manager: BLEDeviceManager = entry_data["manager"]
    async_add_entities([BLEControllerSwitch(entry_data["data"], manager)])


class BLEControllerSwitch(SwitchEntity):
    """BLE GATT write 기반 스위치 엔티티."""

    _attr_has_entity_name = True

    def __init__(self, data: dict, manager: BLEDeviceManager) -> None:
        self._manager = manager
        self._data = data
        self._mac: str = self._data[CONF_ADDRESS]
        self._name: str = self._data.get(CONF_NAME, f"BLE Switch {self._mac}")
        self._char_uuid: str = self._data[CONF_CHAR_UUID]
        self._data_on = bytes.fromhex(self._data[CONF_DATA_ON])
        self._data_off = bytes.fromhex(self._data[CONF_DATA_OFF])
        self._response: bool = self._data.get(CONF_WRITE_WITH_RESPONSE, False)
        self._notify_uuid: str | None = self._data.get(CONF_NOTIFY_UUID)
        self._notify_on: bytes | None = (
            bytes.fromhex(self._data[CONF_NOTIFY_ON_PATTERN])
            if self._data.get(CONF_NOTIFY_ON_PATTERN)
            else None
        )
        self._notify_off: bytes | None = (
            bytes.fromhex(self._data[CONF_NOTIFY_OFF_PATTERN])
            if self._data.get(CONF_NOTIFY_OFF_PATTERN)
            else None
        )

        self._status_query_data: bytes | None = (
            bytes.fromhex(self._data[CONF_STATUS_QUERY_DATA])
            if self._data.get(CONF_STATUS_QUERY_DATA)
            else None
        )
        self._keep_alive: bool = self._data.get(CONF_KEEP_ALIVE, False)

        self._attr_name = self._name
        self._attr_unique_id = f"{DOMAIN}_switch_{self._mac.replace(':', '_').lower()}"
        self._attr_is_on = None
        self._attr_available = True

        # Persistent notify 구독 등록 (연결 시 자동 구독)
        if self._notify_uuid:
            self._manager.setup_persistent_notify(self._notify_uuid)

        if self._keep_alive and self._status_query_data and self._notify_uuid:
            self._manager.set_on_connect_callback(self._on_connect_query_status)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._mac)},
            "name": self._name,
            "manufacturer": "BLE Device",
        }

    async def _send(self, data: bytes, expected_on: bool) -> None:
        ok = await self._manager.write(
            self._char_uuid,
            data,
            response=self._response,
        )
        self._attr_available = ok
        if ok:
            self._attr_is_on = expected_on
        self.async_write_ha_state()

    async def _on_connect_query_status(self) -> None:
        """keepalive 연결 성공 시 상태 조회."""
        state = await self._manager.query_status(
            self._char_uuid,
            self._status_query_data,
            notify_on_pattern=self._notify_on,
            notify_off_pattern=self._notify_off,
        )
        if state is not None:
            self._attr_is_on = state
            self._attr_available = True
            self.async_write_ha_state()
            _LOGGER.info(
                "[BLE %s] 초기 상태 조회 결과: %s",
                self._mac,
                "ON" if state else "OFF",
            )

    async def async_turn_on(self, **kwargs) -> None:
        await self._send(self._data_on, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._send(self._data_off, False)
