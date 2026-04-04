"""BLE Controller 통합."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ENTITY_TYPE, DOMAIN

PLATFORM_MAP = {
    "switch": "switch",
    "button": "button",
    "select": "select",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """config entry로부터 BLE Controller 셋업."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    entity_type = entry.data.get(CONF_ENTITY_TYPE, "switch")
    platforms = [PLATFORM_MAP.get(entity_type, "switch")]
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """config entry 언로드."""
    entity_type = entry.data.get(CONF_ENTITY_TYPE, "switch")
    platforms = [PLATFORM_MAP.get(entity_type, "switch")]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
