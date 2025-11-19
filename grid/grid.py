import os
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Dict, List, Optional

import gspread
import pandas as pd

# Добавляем родительскую директорию в sys.path если её нет
current_dir = Path(__file__).parent.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from config import DEFAULT_GRID_DAYS, GRID_CREDENTIALS_PATH, WEEKDAY_NAMES

scheduler = None
spreadsheet_url = None
credentials_path = GRID_CREDENTIALS_PATH


class GridScheduler:
    """Класс для работы с расписанием событий через Google Sheets"""

    def __init__(self, spreadsheet_url: str = None, credentials_path: str = None):
        """
        Инициализация подключения к Google Sheets

        Args:
            spreadsheet_url: URL Google таблицы
            credentials_path: Путь к JSON файлу с credentials
        """
        self.spreadsheet_url = spreadsheet_url
        # Если путь к credentials не абсолютный, ищем рядом со скриптом
        if credentials_path and os.path.isabs(credentials_path):
            self.credentials_path = credentials_path
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.credentials_path = os.path.join(
                script_dir, credentials_path or "../credentials.json"
            )
        print(self.credentials_path)
        self.gc = None
        self.spreadsheet = None
        # Список дней недели по умолчанию (будет обновлен после подключения)
        self.days = DEFAULT_GRID_DAYS.copy()

        # Названия дней недели для поиска в названиях листов
        self.weekday_names = WEEKDAY_NAMES

        # Кэш всех листов: {день: DataFrame}
        self._cache_all_sheets: Dict[str, pd.DataFrame] = {}

        # Подключаемся только если есть URL и credentials файл существует
        if self.spreadsheet_url and os.path.exists(self.credentials_path):
            if self.connect():
                # Обновляем список дней из названий листов
                self.days = self._get_days_from_sheets()
                # Загружаем все листы в кэш
                self._load_all_sheets()

    def connect(self) -> bool:
        """Подключение к Google Sheets"""
        if not self.spreadsheet_url:
            return False

        try:
            if os.path.exists(self.credentials_path):
                self.gc = gspread.service_account(filename=self.credentials_path)
            else:
                # Попробуем использовать переменные окружения
                self.gc = gspread.service_account()

            self.spreadsheet = self.gc.open_by_url(self.spreadsheet_url)
            print(f"Успешно подключились к Google Sheets {self.spreadsheet.title}")
            return True

        except Exception as e:
            print(f"Ошибка подключения к Google Sheets: {e}")
            return False

    def _load_all_sheets(self):
        """Загрузка всех листов (дней) в кэш"""
        if not self.spreadsheet:
            return

        print("Загружаем все листы в кэш...")
        for day in self.days:
            try:
                worksheet = self._get_worksheet_for_day(day)
                if not worksheet:
                    print(f"Лист для дня {day} не найден")
                    continue

                data = worksheet.get_all_records()
                df = pd.DataFrame(data)
                self._cache_all_sheets[day] = df
                print(f"Загружен лист: {day} ({len(df)} записей)")

            except Exception as e:
                print(f"Ошибка загрузки листа {day}: {e}")

        print(f"Кэш загружен: {len(self._cache_all_sheets)} листов")

    def refresh_cache(self):
        """Принудительное обновление кэша"""
        self._cache_all_sheets.clear()
        self._load_all_sheets()

    def search_person(self, search_query: str) -> Optional[Dict]:
        """
        Поиск человека по фамилии или фамилии + имени

        Args:
            search_query: Фамилия или "Фамилия Имя" для поиска

        Returns:
            Словарь с данными человека или None если не найден
        """
        search_query = search_query.strip()

        try:
            # Работаем с кэшем
            if self._cache_all_sheets:
                return self._search_in_cache(search_query)
            else:
                print("Кэш пуст")
                return None

        except Exception as e:
            print(f"Ошибка при поиске: {e}")
            return None

    def _match_person(self, full_name: str, search_query: str) -> bool:
        """
        Проверка соответствия ФИО поисковому запросу

        Args:
            full_name: Полное имя из таблицы
            search_query: Поисковый запрос

        Returns:
            True если найдено соответствие
        """
        if pd.isna(full_name):
            return False

        full_name = str(full_name).lower().strip()
        search_query = search_query.lower().strip()

        # Разбиваем поисковый запрос на слова
        search_words = search_query.split()

        if len(search_words) == 1:
            # Поиск только по фамилии
            return search_words[0] in full_name
        else:
            # Поиск по нескольким словам - все должны присутствовать
            return all(word in full_name for word in search_words)

    def _search_in_cache(self, search_query: str) -> Optional[Dict]:
        """Поиск в закэшированных листах"""
        person_data = {"name": "", "phone": "", "position": "", "schedule": {}}

        found = False

        for day in self.days:
            try:
                df = self._cache_all_sheets.get(day)
                if df is None or df.empty:
                    continue

                # Поиск по фамилии или фамилии+имени
                mask = df["Организатор"].apply(
                    lambda x: self._match_person(x, search_query)
                )

                if mask.any():
                    found = True
                    person_row = df[mask].iloc[0]

                    if not person_data["name"]:
                        person_data["name"] = person_row["Организатор"]
                        person_data["phone"] = str(person_row.get("Телефон", ""))
                        person_data["position"] = person_row.get("Должность", "")

                    # Извлекаем расписание на день
                    schedule = self._extract_schedule(person_row, df.columns)
                    person_data["schedule"][day] = schedule

            except Exception as e:
                print(f"Ошибка обработки кэша дня {day}: {e}")
                continue

        return person_data if found else None

    def _extract_schedule(self, person_row, columns) -> List[Dict]:
        """Извлечение расписания из строки данных"""
        schedule = []

        # Получаем временные колонки в порядке следования в таблице
        time_columns = []
        for col in columns:
            if isinstance(col, time) or ":" in str(col):
                time_columns.append(col)

        # НЕ сортируем - берем в порядке колонок в таблице

        # Собираем все активности с их временами
        activities = []
        for time_col in time_columns:
            activity = person_row.get(time_col)
            if pd.notna(activity) and str(activity).strip():
                activities.append({"time": time_col, "activity": str(activity).strip()})

        # Группируем соседние одинаковые активности
        if not activities:
            return schedule
        current_start = activities[0]["time"]
        current_activity = activities[0]["activity"]

        for i in range(1, len(activities)):
            if activities[i]["activity"] != current_activity:
                # Добавляем завершенную активность
                schedule.append(
                    {
                        "start": self._format_time(current_start),
                        "end": self._format_time(activities[i]["time"]),
                        "activity": current_activity,
                    }
                )

                # Начинаем новую активность
                current_start = activities[i]["time"]
                current_activity = activities[i]["activity"]

        # Добавляем последнюю активность
        schedule.append(
            {
                "start": self._format_time(current_start),
                "end": "xx:xx",
                "activity": current_activity,
            }
        )

        return schedule

    def _time_to_minutes(self, time_obj) -> int:
        """Конвертация времени в минуты для сортировки"""
        if isinstance(time_obj, time):
            return time_obj.hour * 60 + time_obj.minute
        elif isinstance(time_obj, str) and ":" in time_obj:
            try:
                h, m = map(int, time_obj.split(":")[:2])
                return h * 60 + m
            except:
                return 0
        return 0

    def _format_time(self, time_obj) -> str:
        """Форматирование времени для вывода"""
        if isinstance(time_obj, time):
            return time_obj.strftime("%H:%M")
        elif isinstance(time_obj, str):
            return time_obj
        return str(time_obj)

    def print_schedule(self, person_schedule: Dict) -> str:
        """Красивый вывод расписания"""
        if not person_schedule:
            print("Человек не найден")
            return
        day_names = {
            "четверг": "четверг",
            "пятница": "пятница",
            "суббота": "суббота",
            "воскресенье": "воскресенье",
        }
        output = {}
        for day in self.days:
            if day not in person_schedule:
                continue
            output[day] = ""
            output[day] += f"{day_names[day]}: \n"

            schedule = person_schedule[day]
            for item in schedule:
                output[day] += (
                    f"    {item['start']} - {item['end']}: {item['activity']} \n"
                )

            output[day] += "\n"
        return output

    def get(self, search_query: str, force_refresh: bool = False):
        """Получение расписания сотрудника для бота"""
        if not search_query:
            return "Ошибка: Введите фамилию или фамилию+имя для поиска"

        if force_refresh:
            self.refresh_cache()

        person_data = self.search_person(search_query)
        if person_data:
            # Возвращаем форматированное расписание
            return self.format_schedule_for_bot(person_data)
        else:
            return f"Сотрудник '{search_query}' не найден"

    def format_time(self, time):
        """Приведение времени в формат xx:xx"""
        # 0:00 => 00:00
        time_string = ""
        time_split = time.split(":")

        if len(time_split[0]) == 1:
            time_string += "0" + time_split[0]
        else:
            time_string += time_split[0]

        time_string += ":" + time_split[1]

        return time_string

    def is_current_activity(self, start_str, end_str, now):
        """Проверка текущей активности"""

        now = now.time()  # получаем часы, минуты, секунды

        start = datetime.strptime(start_str, "%H:%M").time()

        if end_str.lower() != "xx:xx":
            end = datetime.strptime(end_str, "%H:%M").time()
            if start <= end:
                return start <= now < end
            else:
                return now >= start or now < end
        else:
            return now >= start

    def is_past_activity(self, end_str, now):
        """Проверка, завершилась ли активность"""
        now = now.time()

        if end_str.lower() != "xx:xx":
            end = datetime.strptime(end_str, "%H:%M").time()
            return now >= end
        return False

    def format_phone_number(self, phone: str) -> str:
        """Форматирование номера телефона к формату, начинающемуся с 8"""

        phone = phone.strip()
        if not phone:
            return ""

        digits = "".join(filter(str.isdigit, phone))

        if digits.startswith("7"):
            digits = "+" + digits

        elif digits.startswith("8"):
            digits = "+7" + digits[1:]

        if len(digits) < 11:
            digits = "+7" + digits.zfill(10)

        return digits

    def format_schedule_for_bot(self, person_data: Dict) -> str:
        """Форматирование расписания для бота"""

        now = datetime.now()  # получаем объект времени в данный момент
        weekday_now = now.weekday()  # получаем порядковый номер дня недели (-1)

        emoji_current = "📍"

        if not person_data:
            return "Данные не найдены"

        result = f"👀 {person_data['name']}\n"
        result += f"📱 {self.format_phone_number(person_data['phone'])}\n"
        result += f"✏️ {person_data['position']}\n\n"

        day_names = {
            "четверг": [
                "Четверг",
                3,
            ],  # добавил порядковый номер дня недели -1 для проверки текущей активности
            "пятница": ["Пятница", 4],
            "суббота": ["Суббота", 5],
            "воскресенье": ["Воскресенье", 6],
        }

        for day in self.days:
            if day not in person_data["schedule"]:
                continue

            result += f"<b>{day_names[day][0]}</b>\n".upper()

            schedule = person_data["schedule"][day]

            is_current_activity = False
            current_activity_id = None
            for idx, item in enumerate(schedule):
                line = f"{self.format_time(item['start'])} — {self.format_time(item['end'])} {item['activity']}"

                # Проверяем только для текущего дня
                if weekday_now == day_names[day][1]:
                    if (
                        self.is_current_activity(item["start"], item["end"], now)
                        and not is_current_activity
                    ):
                        line = f"<b>{emoji_current} {line}</b>"
                        is_current_activity = True
                        current_activity_id = idx
                    elif self.is_past_activity(item["end"], now):
                        line = f"<s>{line}</s>"

                result += line + "\n"

            result += "\n"

            if weekday_now == day_names[day][1]:
                if current_activity_id is not None:
                    current_activity_text = (
                        f"Сейчас: {schedule[current_activity_id]['activity']}\n"
                    )

                    if current_activity_id + 1 < len(schedule):
                        current_activity_text += f"Следующее: {schedule[current_activity_id + 1]['activity']}\n"
                    else:
                        current_activity_text += "Следующее: свободен\n"
                else:
                    current_activity_text = "Сейчас: свободен\nСледующее: свободен"
            else:
                current_activity_text = ""

        result += "\n" + current_activity_text
        return result.strip()

    def _get_days_from_sheets(self) -> List[str]:
        """Получение дней недели из названий листов"""
        if not self.spreadsheet:
            return self.days  # Возвращаем дни по умолчанию

        try:
            all_worksheets = self.spreadsheet.worksheets()
            found_days = []

            for worksheet in all_worksheets:
                worksheet_name = worksheet.title.lower()
                # Проверяем, содержит ли название листа день недели
                for day in self.weekday_names:
                    if day in worksheet_name:
                        found_days.append(day)
                        print(f"Найден лист с днем недели: {worksheet.title} -> {day}")
                        break

            # Удаляем дубликаты и сортируем по порядку дней недели
            unique_days = []
            for day in self.weekday_names:
                if day in found_days and day not in unique_days:
                    unique_days.append(day)

            return unique_days if unique_days else self.days

        except Exception as e:
            print(f"Ошибка получения дней из листов: {e}")
            return self.days

    def _get_worksheet_for_day(self, day: str):
        """Получение листа для определенного дня недели"""
        if not self.spreadsheet:
            return None

        try:
            all_worksheets = self.spreadsheet.worksheets()
            for worksheet in all_worksheets:
                worksheet_name = worksheet.title.lower()
                if day in worksheet_name:
                    return worksheet

            return None

        except Exception as e:
            print(f"Ошибка получения листа для дня {day}: {e}")
            return None

    def format_important_numbers_for_bot(self):
        """Форматирование важных номеров для бота"""

        data = self.get_important_numbers()
        string = ""

        if not data:
            return "Нет данных"

        # print(data)

        for emp in data:
            print(emp)
            name = emp["имя"]
            phone = emp["телефон"]
            job_title = emp["должность"]
            string += (
                f"<b>{name}</b>\n{self.format_phone_number(phone)}\n{job_title}\n\n"
            )
        return string

    def get_important_numbers(self):
        """Получение листа с важными номерами"""

        if not self.spreadsheet:
            return None

        try:
            all_worksheets = self.spreadsheet.worksheets()

            for worksheet in all_worksheets:
                worksheet_name = worksheet.title.lower()

                if worksheet_name == "важные номера":
                    data = worksheet.get_all_records()
                    df = pd.DataFrame(data)
                    df["Телефон"] = (
                        df["Телефон"].astype(str).apply(self.format_phone_number)
                    )  # преобразовываем все номера к международному формату

                    try:
                        dict_data = df.to_dict(orient="records")

                        dict_format = [
                            {k.lower().strip(): v for k, v in d.items()}
                            for d in dict_data
                        ]
                        # print(dict_format)
                        # print( type(dict_format))
                        return dict_format

                    except Exception as er:
                        print(er)
                        return None

        except Exception as e:
            print(f"Ошибка получеиня листа для листа Важные номера: {e}")
            return None


def init_scheduler(spreadsheet_url: str = None, credentials_path: str = None):
    """Инициализация планировщика"""
    global scheduler
    scheduler = GridScheduler(
        spreadsheet_url=spreadsheet_url, credentials_path=credentials_path
    )
    return scheduler


if __name__ == "__main__":
    scheduler = init_scheduler(
        spreadsheet_url=os.getenv("SPREADSHEET_URL"),
        credentials_path=GRID_CREDENTIALS_PATH,
    )
    # print(scheduler.get("Бенца"))
    print(scheduler.format_important_numbers_for_bot())
