"""BLE Controller 버튼 플랫폼."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble_client import BLEDeviceManager
from .const import (
    CONF_CHAR_UUID,
    CONF_DATA_PRESS,
    CONF_WRITE_WITH_RESPONSE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """버튼 엔티티 셋업."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    manager: BLEDeviceManager = entry_data["manager"]
    async_add_entities([BLEControllerButton(entry_data["data"], manager)])


class BLEControllerButton(ButtonEntity):
    """BLE GATT write 기반 버튼 엔티티."""

    _attr_has_entity_name = True

    def __init__(self, data: dict, manager: BLEDeviceManager) -> None:
        self._manager = manager
        self._data = data
        self._mac: str = self._data[CONF_ADDRESS]
        self._name: str = self._data.get(CONF_NAME, f"BLE Button {self._mac}")
        self._char_uuid: str = self._data[CONF_CHAR_UUID]
        self._data_press = bytes.fromhex(self._data[CONF_DATA_PRESS])
        self._response: bool = self._data.get(CONF_WRITE_WITH_RESPONSE, False)

        self._attr_name = self._name
        self._attr_unique_id = f"{DOMAIN}_button_{self._mac.replace(':', '_').lower()}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._mac)},
            "name": self._name,
            "manufacturer": "BLE Device",
        }

    async def async_press(self) -> None:
        ok = await self._manager.write(
            self._char_uuid,
            self._data_press,
            response=self._response,
        )
        if not ok:
            _LOGGER.warning("BLE 버튼 커맨드 전송 실패: %s", self._mac)
