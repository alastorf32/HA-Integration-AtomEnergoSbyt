import re
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_LS_NUMBER, CONF_COUNTERS_DATA
from .atomsbt_lib import AtomEnergoSender, custom_log

# Маппинг для определения типа сенсора по имени
SENSOR_NAME_MAP = {
    "Холодное водоснабжение": "cold_water",
    "Горячее водоснабжение": "warm_water",
    "Электроснабжение": "electro",
}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Настройка сенсоров при создании записи конфигурации."""
    # Получаем данные из конфигурации
    custom_log(f"async_setup_entry::start")
    data = hass.data[DOMAIN][config_entry.entry_id]
    ls_number = data[CONF_LS_NUMBER]
    counters_data = data[CONF_COUNTERS_DATA].get("counters", {})
    custom_log(f"async_setup_entry:: ls_number [{ls_number}]")

    sensors = []
    #for counter_id, counter_info in counters_data.items():
    for counter_info in counters_data:
        name = counter_info.get("name", "").strip()
        previous_value = counter_info.get("previous_value")
        zavod_nomer = counter_info.get("zavod_nomer")
        fields = counter_info.get("fields", [])
        counter_id = "0"
        last_date_readings = ""
        check_avg = ""
        tarifnost = ""
        service_number = ""
        tariff_name = ""
        if fields:
            counter_id = _extract_counter_id_from_fields(fields)
            last_date_readings = _extract_value_from_fields(fields, "DatePok")
            check_avg = _extract_value_from_fields(fields, "check_avg")
            tarifnost = _extract_value_from_fields(fields, "Tarifnost")
            service_number = _extract_value_from_fields(fields, "NomerUslugi")
            tariff_name = _extract_value_from_fields(fields, "NazvanieTarifa")
            
        # Определяем тип сенсора по ключевому слову в name
        sensor_type = "unknown"
        for prefix, sensor_key in SENSOR_NAME_MAP.items():
            if name.startswith(prefix):
                sensor_type = sensor_key
                break

        # Создаём сенсор с уникальным ID на основе ID счётчика
        custom_log(f"async_setup_entry:: sensors.append(AtomCounterSensor) ls_number [{ls_number}], counter_id [{counter_id}], counter_name [{name}], sensor_type [{sensor_type}], state [{previous_value}], last_date_readings [{last_date_readings}], check_avg [{check_avg}], tarifnost [{tarifnost}], service_number {[service_number]}, tariff_name [{tariff_name}], zavod_nomer [{zavod_nomer}]")
        sensors.append(AtomCounterSensor(
            ls_number=ls_number,
            counter_id=counter_id,
            counter_name=name,
            sensor_type=sensor_type,
            state=previous_value,
            last_date_readings=last_date_readings,
            check_avg=check_avg,
            tarifnost=tarifnost,
            service_number=service_number,
            tariff_name=tariff_name,
            zavod_nomer=zavod_nomer
        ))

    async_add_entities(sensors)

def _extract_counter_id_from_fields(fields):
    """Извлекаем ID счетчика из поля в fields, если оно присутствует."""
    # Регулярное выражение для извлечения ID из строки
    pattern = r"counters\[(\d+)\]"
    
    for field in fields:
        # Если поле - строка, пытаемся найти ID в самой строке
        if isinstance(field, str):
            match = re.search(pattern, field)
            if match:
                return match.group(1)  # Извлекаем номер ID и возвращаем его
        
        # Если поле - словарь, пытаемся найти 'field_name' и извлекаем ID из него
        elif isinstance(field, dict):
            match = re.search(pattern, field.get("field_name", ""))
            if match:
                return match.group(1)  # Извлекаем номер ID и возвращаем его
    return None
    
def _extract_value_from_fields(fields, value):
    """Ищет в fields элемент с [DatePok] и извлекает значение после него."""
    date_pok_values = []
    # Проходим по всем полям
    for field in fields:
        # Проверяем, если имя поля заканчивается на '[DatePok]'
        match = re.search(rf"\[{value}\]$", field)
        if match:
            # Если найдено, добавляем соответствующее значение в список
            date_pok_values.append(fields[field])  # предполагаем, что значение находится в поле с таким именем
    # Возвращаем все найденные значения или None, если ничего не найдено
    return date_pok_values if date_pok_values else None

class AtomCounterSensor(SensorEntity):
    """Сенсор для счетчиков."""
    
    def __init__(self, ls_number, counter_id, counter_name, sensor_type, state, last_date_readings, check_avg, tarifnost, service_number, tariff_name, zavod_nomer):
        self._ls_number = ls_number
        self._counter_id = counter_id
        self._sensor_type = sensor_type
        self._state = state
        self._last_date_readings = last_date_readings
        self._check_avg = check_avg
        self._tarifnost = tarifnost
        self._service_number = service_number
        self._tariff_name = tariff_name
        self._sensor_name = self._get_sensor_name(counter_name)
        self._unit_of_measurement = self._get_unit_of_measurement(counter_name)
        self._device_class = self._get_device_class(counter_name)

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
        return f"atomsbt_{self._ls_number}_{self._sensor_name}_{self._counter_id}"

    @property
    def unique_id(self):
        """Уникальный идентификатор сенсора."""
        return f"atomsbt_{self._ls_number}_{self._sensor_name}_{self._counter_id}"

    @property
    def state(self):
        """Состояние сенсора (значение счетчика)."""
        return self._state or "Не найден"

    @property
    def extra_state_attributes(self):
        """Возвращаем дополнительные атрибуты для сенсора."""
        return {
            "Лицевой счет": self._ls_number,
            "ID счетчика": self._counter_id,
            "Дата последней передачи показаний": self._last_date_readings,
            "Последние показания": self._state,
            "CheckAVG": self._check_avg,
            "Tarifnost": self._tarifnost,
            "Номер услуги": self._service_number,
            "Наименование тарифа": self._tariff_name,
        }

    @property
    def device_class(self):
        """Тип устройства (класс)."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Единицы измерения."""
        return self._unit_of_measurement