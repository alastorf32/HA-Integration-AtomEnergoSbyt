from homeassistant.helpers.entity import Entity
from .const import DOMAIN, CONF_LS_NUMBER

async def async_setup_entry(hass, config_entry, async_add_entities):
    ls_number = config_entry.data[CONF_LS_NUMBER]
    meter_id = config_entry.data.get('meter_id')
    payload = config_entry.data.get('payload')

    async_add_entities([
        AtomSensor(ls_number, meter_id, payload)
    ])

class AtomSensor(Entity):
    def __init__(self, ls_number, meter_id, payload):
        self._ls_number = ls_number
        self._meter_id = meter_id
        self._payload = payload

    @property
    def name(self):
        return f"atom_{self._ls_number}"

    @property
    def unique_id(self):
        return f"atom_{self._ls_number}"

    @property
    def state(self):
        return self._meter_id or "Не найден"

    @property
    def extra_state_attributes(self):
        # Возвращаем нужные атрибуты из payload
        return {
            "Номер счетчика": self._meter_id,
            "Все поля счетчика": self._payload.get('counter_fields', {}),
            "Токены": self._payload.get('service_tokens', {}),
        }