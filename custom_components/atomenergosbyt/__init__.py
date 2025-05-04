from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, CONF_LS_NUMBER, CONF_COUNTERS_DATA

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Сохраняем номер счёта в глобальные данные HA."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_LS_NUMBER: entry.data.get(CONF_LS_NUMBER),
        CONF_COUNTERS_DATA: entry.data.get(CONF_COUNTERS_DATA),
    }
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
    
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Удаление записи конфигурации."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok