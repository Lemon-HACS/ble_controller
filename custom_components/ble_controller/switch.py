"""BLE Controller 스위치 플랫폼."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble_client import BLEDeviceManager
from .const import (
    CONF_CHAR_UUID,
    CONF_DATA_OFF,
    CONF_DATA_ON,
    CONF_NOTIFY_OFF_PATTERN,
    CONF_NOTIFY_ON_PATTERN,
    CONF_NOTIFY_UUID,
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
    manager: BLEDeviceManager = hass.data[DOMAIN][entry.entry_id]["manager"]
    async_add_entities([BLEControllerSwitch(entry, manager)])


class BLEControllerSwitch(SwitchEntity):
    """BLE GATT write 기반 스위치 엔티티."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, manager: BLEDeviceManager) -> None:
        self._manager = manager
        self._data = entry.data
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

        self._attr_name = self._name
        self._attr_unique_id = f"{DOMAIN}_switch_{self._mac.replace(':', '_').lower()}"
        self._attr_is_on = None
        self._attr_available = True

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._mac)},
            "name": self._name,
            "manufacturer": "BLE Device",
        }

    async def _send(self, data: bytes, expected_on: bool) -> None:
        if self._notify_uuid:
            ok, state = await self._manager.write_and_notify(
                self._char_uuid,
                data,
                response=self._response,
                notify_uuid=self._notify_uuid,
                notify_on_pattern=self._notify_on,
                notify_off_pattern=self._notify_off,
            )
            self._attr_available = ok
            if ok:
                self._attr_is_on = state if state is not None else expected_on
        else:
            ok = await self._manager.write(
                self._char_uuid,
                data,
                response=self._response,
            )
            self._attr_available = ok
            if ok:
                self._attr_is_on = expected_on
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        await self._send(self._data_on, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._send(self._data_off, False)
