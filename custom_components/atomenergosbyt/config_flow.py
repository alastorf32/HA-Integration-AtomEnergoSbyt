## Форма взаимодействия с пользователем - при добавлении интеграции

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.helpers import selector
from typing import Any
from . import const
from .atomsbt_lib import AtomEnergoSender, custom_log

class atomenergosbytConfigFlow(config_entries.ConfigFlow, domain=const.DOMAIN):
    VERSION = 1
    
    # Добавление интеграции (регистрация лицевого счета)
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is None:
            # Первый вызов - показываем форму
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(const.CONF_LS_NUMBER): cv.string
                }),
                errors=errors
            )
    
        ls_number = user_input.get(const.CONF_LS_NUMBER, "").strip()
        custom_log(f"async_step_user:ls_number [{ls_number}]")
    
        # Проверка: только цифры
        if not ls_number.isdigit():
            errors["base"] = "invalid_ls"
            custom_log(f"async_step_user:ls_number NOT isdigit()")
        else:
            # Проверка на дублирование
            for entry in self._async_current_entries():
                if entry.data.get(const.CONF_LS_NUMBER) == ls_number:
                    errors["base"] = "exist_ls"
                    custom_log(f"async_step_user:ls_number уже существует")
                    break
    
        if not errors:
            # Проверяем данные с сервера
            sender = AtomEnergoSender(ls_number)
            parseData = await self.hass.async_add_executor_job(sender.get_meter_id)
            if "meter_id" in parseData:
                meter_id = parseData["meter_id"]
            elif len(parseData["counters"]) == 0:
                meter_id = const.ERR_NO_COUNTERS
            else:
                meter_id = 0
            custom_log(f"async_step_user:parseData[meter_id] = {meter_id}")
    
            if meter_id == "None":
                errors["base"] = "invalid_ls"
            elif meter_id == const.ERR_NO_DATA_PERIOD:
                self.ls_number = ls_number
                return self.async_show_form(
                    step_id="confirm_continue",
                    data_schema=vol.Schema({
                        vol.Required("confirm", default=False): bool
                    }),
                    description_placeholders={
                        "warning_message": "В настоящее время невозможно получить сведения по электросчетчикам. Они доступны с 5 по 25 число ежемесячно. Продолжить регистрацию?"
                    }
                )
            elif meter_id == const.ERR_LS_NOT_FOUND:
                errors["base"] = "ls_not_founded"
            elif meter_id == const.ERR_LS_CHECK:
                errors["base"] = "ls_check_error"
            elif meter_id == const.ERR_NO_COUNTERS:
                errors["base"] = "counters_not_founded"
            elif meter_id == const.ERR_RESPONSE_CODE:
                errors["base"] = "http_response_error"
            elif meter_id == const.ERR_TOKEN_EXTRACT:
                errors["base"] = "http_token_error"
            elif meter_id == const.ERR_UNKNOWN_ERROR:
                errors["base"] = "unknown_error"
            else:
                return self.async_create_entry(
                    title=f"Лицевой счет № {ls_number}",
                    data={const.CONF_LS_NUMBER: ls_number, const.CONF_COUNTERS_DATA: parseData}
                )
    
        # Показываем форму заново с ошибками
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(const.CONF_LS_NUMBER): cv.string
            }),
            errors=errors
        )
                
    async def async_step_confirm_continue(self, user_input: dict[str, Any] | None = None):
        errors = {}
    
        if user_input is not None:
            if user_input.get("confirm"):
                # Пользователь согласился продолжить регистрацию
                return self.async_create_entry(
                    title=f"Лицевой счет № {ls_number}",
                    data={const.CONF_LS_NUMBER: self.ls_number}
                )
            else:
                # Пользователь отказался
                return self.async_abort(reason="user_declined")
                
        # ✅ Возвращаем форму, если данные ещё не введены
        return self.async_show_form(
            step_id="confirm_continue",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): bool
            }),
            description_placeholders={
                "warning_message": "В настоящее время невозможно получить сведения по электросчётчику. Продолжить регистрацию?"
            },
            errors=errors
        )
