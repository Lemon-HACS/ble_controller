"""BLE Controller 통합."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .ble_client import BLEDeviceManager
from .const import CONF_ENTITY_TYPE, CONF_KEEP_ALIVE, CONF_KEEPALIVE_INTERVAL, DEFAULT_KEEPALIVE_INTERVAL, DOMAIN

PLATFORM_MAP = {
    "switch": "switch",
    "button": "button",
    "select": "select",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """config entry로부터 BLE Controller 셋업."""
    hass.data.setdefault(DOMAIN, {})

    merged = {**entry.data, **entry.options}
    mac = merged[CONF_ADDRESS]
    keep_alive = merged.get(CONF_KEEP_ALIVE, False)
    keepalive_interval = merged.get(CONF_KEEPALIVE_INTERVAL, DEFAULT_KEEPALIVE_INTERVAL)
    manager = BLEDeviceManager(hass, mac, keep_alive=keep_alive, keepalive_interval=keepalive_interval)
    manager.start_keepalive()

    hass.data[DOMAIN][entry.entry_id] = {
        "data": merged,
        "manager": manager,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    entity_type = merged.get(CONF_ENTITY_TYPE, "switch")
    platforms = [PLATFORM_MAP.get(entity_type, "switch")]
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """옵션 변경 시 엔트리 리로드."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """config entry 언로드."""
    entity_type = entry.data.get(CONF_ENTITY_TYPE, "switch")
    platforms = [PLATFORM_MAP.get(entity_type, "switch")]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if entry_data and "manager" in entry_data:
            await entry_data["manager"].async_shutdown()
    return unload_ok
