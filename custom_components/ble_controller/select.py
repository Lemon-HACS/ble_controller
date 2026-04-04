"""BLE Controller 셀렉트 플랫폼."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble_client import ble_write
from .const import (
    CONF_CHAR_UUID,
    CONF_OPTIONS,
    CONF_WRITE_WITH_RESPONSE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """셀렉트 엔티티 셋업."""
    async_add_entities([BLEControllerSelect(hass, entry)])


class BLEControllerSelect(SelectEntity):
    """BLE GATT write 기반 셀렉트 엔티티."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._data = entry.data
        self._mac: str = self._data[CONF_ADDRESS]
        self._name: str = self._data.get(CONF_NAME, f"BLE Select {self._mac}")
        self._char_uuid: str = self._data[CONF_CHAR_UUID]
        self._response: bool = self._data.get(CONF_WRITE_WITH_RESPONSE, False)

        # options: [{"label": "모드1", "data": "0aa501"}, ...]
        self._options_config: list[dict] = self._data.get(CONF_OPTIONS, [])
        self._label_to_data: dict[str, bytes] = {
            opt["label"]: bytes.fromhex(opt["data"])
            for opt in self._options_config
        }

        self._attr_name = self._name
        self._attr_unique_id = f"{DOMAIN}_select_{self._mac.replace(':', '_').lower()}"
        self._attr_options = [opt["label"] for opt in self._options_config]
        self._attr_current_option = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._mac)},
            "name": self._name,
            "manufacturer": "BLE Device",
        }

    async def async_select_option(self, option: str) -> None:
        data = self._label_to_data.get(option)
        if data is None:
            _LOGGER.error("알 수 없는 옵션: %s", option)
            return

        ok = await ble_write(
            self.hass, self._mac, self._char_uuid, data,
            response=self._response,
        )
        if ok:
            self._attr_current_option = option
            self.async_write_ha_state()
        else:
            _LOGGER.warning("BLE 셀렉트 커맨드 전송 실패: %s", self._mac)
