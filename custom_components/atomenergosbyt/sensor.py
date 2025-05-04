from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_LS_NUMBER, CONF_COUNTERS_DATA

# Маппинг для определения типа сенсора по имени
SENSOR_NAME_MAP = {
    "Холодное водоснабжение": "cold_water",
    "Горячее водоснабжение": "warm_water",
    "Электроснабжение": "electro",
}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Настройка сенсоров при создании записи конфигурации."""
    # Получаем данные из конфигурации
    data = hass.data[DOMAIN][config_entry.entry_id]
    ls_number = data[CONF_LS_NUMBER]
    counters_data = data[CONF_COUNTERS_DATA].get("counters", {})
    
    # Создаем список сенсоров
    sensors = []
    for counter_id, counter_info in counters_data.items():
        sensors.append(AtomCounterSensor(ls_number, counter_id, counter_info))

    # Добавляем сенсоры в HA
    async_add_entities(sensors)

class AtomCounterSensor(SensorEntity):
    """Сенсор для счетчиков."""
    
    def __init__(self, ls_number, meter_id, counter_info):
        """Инициализация сенсора."""
        self._ls_number = ls_number
        self._meter_id = meter_id
        self._counter_info = counter_info
        self._state = counter_info.get("previous_value")
        self._sensor_name = self._get_sensor_name(counter_info.get("name"))
        self._unit_of_measurement = self._get_unit_of_measurement(counter_info.get("name"))
        self._device_class = self._get_device_class(counter_info.get("name"))

    def _get_sensor_name(self, name):
        """Определение типа сенсора по имени счетчика."""
        for key, value in SENSOR_NAME_MAP.items():
            if name.startswith(key):
                return value
        return "unknown"

    def _get_unit_of_measurement(self, name):
        """Устанавливаем единицы измерения в зависимости от типа счетчика."""
        if "Электроснабжение" in name:
            return "kWh"
        elif "водоснабжение" in name:
            return "m³"
        return "unit"

    def _get_device_class(self, name):
        """Устанавливаем тип устройства в зависимости от типа счетчика."""
        if "Электроснабжение" in name:
            return "energy"
        elif "водоснабжение" in name:
            return "water"
        return "measurement"

    @property
    def name(self):
        """Имя сенсора."""
        return f"atom_{self._ls_number}_{self._sensor_name}_{self._meter_id}"

    @property
    def unique_id(self):
        """Уникальный идентификатор сенсора."""
        return f"atom_{self._ls_number}_{self._meter_id}"

    @property
    def state(self):
        """Состояние сенсора (значение счетчика)."""
        return self._state or "Не найден"

    @property
    def extra_state_attributes(self):
        """Возвращаем дополнительные атрибуты для сенсора."""
        return {
            "Номер счетчика": self._meter_id,
            "Все поля счетчика": self._counter_info.get("counter_fields", {}),
        }

    @property
    def device_class(self):
        """Тип устройства (класс)."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Единицы измерения."""
        return self._unit_of_measurement