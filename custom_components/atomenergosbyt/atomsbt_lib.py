import requests
import urllib3
import logging
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime
from logging.handlers import RotatingFileHandler
from . import const

# --- Настройка логирования ---
LOG_DIR = '/config/custom_components/atomenergosbyt'
LOG_FILE_PATH = os.path.join(LOG_DIR, '_atomsbt.log')

os.makedirs(LOG_DIR, exist_ok=True)
logger = logging.getLogger("kolatom_logger")
logger.setLevel(logging.DEBUG)

handler = RotatingFileHandler(
    LOG_FILE_PATH,
    maxBytes=100 * 1024 * 1024,  # 100 МБ
    backupCount=5  # 5 резервных копий
)
formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%d.%m.%Y %H:%M:%S')
handler.setFormatter(formatter)

# Чтобы не добавлять несколько обработчиков при повторном импорте
if not logger.handlers:
    logger.addHandler(handler)

# --- Функция для логирования ---
def custom_log(message: str):
    logger.info(message)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class AtomEnergoSender:
    def __init__(self, account_number: str):
        self.base_url = "https://lkfl.atomsbt.ru"
        self.session = requests.Session()
        self.account_number = account_number
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })
        self.session.verify = False
        self.cookies = None

    def parse_counter_data(self, html_content):
        """Парсит все карточки счетчиков на странице, не группируя по типу ресурса."""
        soup = BeautifulSoup(html_content, 'html.parser')
        counters = []

        # 1. Найти все карточки счётчиков
        card_blocks = soup.find_all("div", class_="card")
        #for idx, card in enumerate(card_blocks):
#            print(f"Card {idx}:", card.prettify())

        #for card in card_blocks:
        for idx, card in enumerate(card_blocks[1:]):  # Начинаем с 1-го элемента
            counter = {
                "name": None,  # "Холодное водоснабжение", "Электроснабжение", и т.д.
                "zavod_nomer": None,  # № 12345678
                "previous_value": None,  # Последнее показание
                "fields": {}  # Все input name/value (text + hidden)
            }

            # Название счётчика (тип услуги)
            strong_tag = card.find("strong")
            if strong_tag:
                counter_name = strong_tag.get_text(strip=True)
                if counter_name.endswith("."):
                    counter_name = counter_name[:len(counter_name) - 1]
                counter["name"] = counter_name

            # Заводской номер (из <h2> "№ ...")
            h2_tags = card.find_all("h2")
            for h2 in h2_tags:
                if "№" in h2.text:
                    counter["zavod_nomer"] = h2.get_text(strip=True).split("№")[-1].strip()
                    break

            # Предыдущее показание (ищем div, содержащий только цифры)
            float_rights = card.find_all("div", class_="float-right")
            for fr in float_rights:
                if "Предыдущее показание" in fr.get_text(strip=True):
                    value_div = fr.find("div")
                    if value_div:
                        #counter["previous_value"] = value_div.get_text(strip=True).split()[0]  # Получаем только число
                        previous_value_text = value_div.get_text(strip=True)

                        # Используем регулярное выражение для извлечения только цифр
                        match = re.search(r'\d+', previous_value_text)
                        if match:
                            counter["previous_value"] = match.group(0)  # Сохраняем только найденное число
                    break

            # Все input поля
            for input_field in card.find_all("input"):
                name = input_field.get("name")
                value = input_field.get("value", "")
                if name:
                    counter["fields"][name] = value

            counters.append(counter)

        # 2. Общие токены (вне карточек)
        service_tokens = {}
        for token_name in ["lk_add_value_token"]:
            token_input = soup.find("input", {"name": token_name})
            if token_input:
                service_tokens[token_name] = token_input.get("value")

        return {
            "counters": counters,
            "service_tokens": service_tokens
        }

    def get_meter_id(self):
        """Получаем номер счетчика с правильными параметрами запроса"""
        # Сначала загружаем страницу для получения токенов
        custom_log("[AtomEnergoSender::get_meter_id] [start]")
        init_url = f"{self.base_url}/lk_auth/counters.php?source=ABINTERNETBR"
        try:
            response = self.session.get(init_url, timeout=10)
            response.raise_for_status()
            self.cookies = response.cookies.get_dict() # Сохраняем cookies для последующих запросов
            custom_log(f"[AtomEnergoSender::get_meter_id] [Запрос к сайту kolatom.ru по ЛС {self.account_number}. Статус {response.status_code}]") 
            custom_log(f"[AtomEnergoSender::get_meter_id] [First (empty) Query. response.status_code [{response.status_code}]")
            #custom_log(f"[AtomEnergoSender::get_meter_id] [First (empty) Query. response.text [ {response.text}]")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # Парсим токены из HTML
            custom_log(f"[AtomEnergoSender::get_meter_id] [parsing Tokens]")
            csrf_token = soup.find('meta', {'name': 'csrf-token-value'}).get('content')
            lk_token = soup.find('input', {'name': 'lk_add_value_token'}).get('value')
            custom_log(f"[AtomEnergoSender::get_meter_id] [csrf_token] = [{csrf_token}]")
            custom_log(f"[AtomEnergoSender::get_meter_id] [lk_token] = [{lk_token}]")
            if not all([csrf_token, lk_token]):
                raise ValueError("Не удалось извлечь токены из страницы")

        except Exception as e:
            custom_log(f"Ошибка при получении токенов: {str(e)}")
            return {"meter_id": const.ERR_TOKEN_EXTRACT}

        # Формируем правильный запрос
        url = f"{self.base_url}/lk_auth/counters.php?source=ABINTERNETBR"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': self.base_url,
            'Referer': f"{self.base_url}/lk_auth/counters.php?source=ABINTERNETBR",
        }

        form_data = {
            'ls': self.account_number,
            'lk_add_value_token': lk_token,
            'action': 'checkLs',
            'csrftoken': csrf_token
        }

        try:
            response = self.session.post(
                url,
                headers=headers,
                data=form_data,
                cookies=self.cookies,  # Используем сохраненные cookies
                timeout=15
            )

            #custom_log(f"[AtomEnergoSender::get_meter_id] При загрузке - lk_add_value_token [ {lk_token} ]\ncsrftoken [ {csrf_token} ]")
            custom_log(f"[AtomEnergoSender::get_meter_id] [Second (needed) Query. response.status_code [{response.status_code}]")
            #custom_log(f"[AtomEnergoSender::get_meter_id] [Second (needed) Query. response.text [ {response.text}]")
            if response.status_code == 200:
                data = self.parse_counter_data(response.text)

                # Сохраняем HTML для отладки
                with open('counter_page.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                matching_divs = [] # Найдём все div'ы, а потом фильтруем по тексту
                cntr = 0
                err = 0
                for div in soup.find_all('div'):
                    cntr += 1
                    clean_text = ' '.join(div.get_text().split())
                    custom_log(f"[AtomEnergoSender::get_meter_id] [FindAlert] [cntr = {cntr}], [div] = [{clean_text}]")
                    if div and div.get_text(strip=True).startswith("Занесение показаний возможно с 5 по 25"):
                        matching_divs.append(div)
                        err = const.ERR_NO_DATA_PERIOD
                        break
                    if div and div.get_text(strip=True).startswith("Лицевой счет не найден"):
                        matching_divs.append(div)
                        err = const.ERR_LS_NOT_FOUND
                        break
                    if div and div.get_text(strip=True).startswith("Ошибка проверки лицевого счета"):
                        matching_divs.append(div)
                        err = const.ERR_LS_CHECK
                        break
                    if div and div.get_text(strip=True).startswith("Отсутствуют счётчики для занесения показаний"):
                        matching_divs.append(div)
                        err = const.ERR_NO_COUNTERS
                        break
                # Проверка
                if matching_divs:
                    if err == -1:
                        custom_log("[AtomEnergoSender::get_meter_id] [Ошибка] Получено сообщение о невозможности занесения показаний вне периода с 5 по 25 число!")
                    if err == -2:
                        custom_log("[AtomEnergoSender::get_meter_id] [Ошибка] Получено сообщение об отсутствии лицевого счета")
                    if err == -3:
                        custom_log("[AtomEnergoSender::get_meter_id] [Ошибка] Получено сообщение об отсутствии электросчетчиков")
                    return {"meter_id": str(err)}
                else:
                    custom_log("[AtomEnergoSender::get_meter_id] Сообщений с 5 по 25 число НЕТ]")
                    # Анализируем результаты
                    if len(data["counters"]) == 0:
                        custom_log("[AtomEnergoSender::get_meter_id] [Ошибка] Не удалось определить номер счетчика")
                        return {"meter_id": "None"}
                    return data
            else:
                custom_log(f"[AtomEnergoSender::get_meter_id] [Ошибка] HTTP: {response.status_code}")
                return {"meter_id": const.ERR_RESPONSE_CODE}
        except Exception as e:
            custom_log(f"[AtomEnergoSender::get_meter_id] [Ошибка] при получении токенов: {str(e)}")
            return {"meter_id": const.ERR_TOKEN_EXTRACT}

    def prepare_submission(self, counter_data, meter_value):
        """Подготавливаем данные для отправки"""
        form_data = {
            # Основное поле с показаниями
            counter_data['value_field']['name']: meter_value,
            # Все поля счетчика
            **counter_data['counter_fields'],
            # Сервисные токены
            **counter_data['service_tokens'],
            'action': 'add',
            'ls': self.account_number #'ls': nomer_ls
        }
        return form_data

    def send_reading(self, meter_id, value):
        """Отправка показаний с полной эмуляцией браузера"""
        url = f"{self.base_url}/lk_auth/counters.php?source=ABINTERNETBR"
        payload = self.prepare_submission(meter_id, value)
        custom_log(f"[AtomEnergoSender::send_reading] [lk_add_value_token] = [ {payload['lk_add_value_token']} ]\ncsrftoken [ {payload['csrftoken']} ]")
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': payload['csrftoken'],
            'Origin': self.base_url,
            'Referer': f"{self.base_url}/lk_auth/counters.php?source=ABINTERNETBR",
        }
#        custom_log(payload)

        try:
            response = self.session.post(
                url,
                headers=headers,
                data=payload,
                cookies=self.cookies,  # Используем сохраненные cookies
                timeout=15
            )
            custom_log(f"[AtomEnergoSender::send_reading] Статус код: {response.status_code}")
            custom_log(f"[AtomEnergoSender::send_reading] Ответ сервера: {response.text}")

            return response.status_code == 200

        except Exception as e:
            custom_log(f"Ошибка отправки: {str(e)}")
            return False