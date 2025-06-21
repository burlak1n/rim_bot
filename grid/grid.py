import gspread
import pandas as pd
from datetime import time
from typing import Dict, List, Optional
import os
import sys
from pathlib import Path

# Добавляем родительскую директорию в sys.path если её нет
current_dir = Path(__file__).parent.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from config import GRID_CREDENTIALS_PATH, DEFAULT_GRID_DAYS, WEEKDAY_NAMES

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
            self.credentials_path = os.path.join(script_dir, credentials_path or "../credentials.json")
        print(self.credentials_path)
        self.gc = None
        self.spreadsheet = None
        # Список дней недели по умолчанию (будет обновлен после подключения)
        self.days = DEFAULT_GRID_DAYS.copy()
        
        # Названия дней недели для поиска в названиях листов
        self.weekday_names = WEEKDAY_NAMES
        # Подключаемся только если есть URL и credentials файл существует
        if self.spreadsheet_url and os.path.exists(self.credentials_path):
            if self.connect():
                # Обновляем список дней из названий листов
                self.days = self._get_days_from_sheets()
        
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
            # Работаем только с Google Sheets
            if self.spreadsheet:
                return self._search_in_google_sheets(search_query)
            else:
                print("Нет подключения к Google Sheets")
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
    
    def _search_in_google_sheets(self, search_query: str) -> Optional[Dict]:
        """Поиск в Google Sheets"""
        person_data = {
            'name': '',
            'phone': '',
            'position': '',
            'schedule': {}
        }
        
        found = False
        
        for day in self.days:
            try:
                worksheet = self._get_worksheet_for_day(day)
                if not worksheet:
                    print(f"Лист для дня {day} не найден")
                    continue
                    
                data = worksheet.get_all_records()
                df = pd.DataFrame(data)
                
                # Поиск по фамилии или фамилии+имени
                mask = df['Организатор'].apply(lambda x: self._match_person(x, search_query))
                
                if mask.any():
                    found = True
                    person_row = df[mask].iloc[0]
                    
                    if not person_data['name']:
                        person_data['name'] = person_row['Организатор']
                        person_data['phone'] = str(person_row.get('Телефон', ''))
                        person_data['position'] = person_row.get('Должность', '')
                    
                    # Извлекаем расписание на день
                    schedule = self._extract_schedule(person_row, df.columns)
                    person_data['schedule'][day] = schedule
                    
            except Exception as e:
                print(f"Ошибка обработки листа {day}: {e}")
                continue
        
        return person_data if found else None
    
    def _extract_schedule(self, person_row, columns) -> List[Dict]:
        """Извлечение расписания из строки данных"""
        schedule = []
        
        # Получаем временные колонки в порядке следования в таблице
        time_columns = []
        for col in columns:
            if isinstance(col, time) or ':' in str(col):
                time_columns.append(col)
        
        # НЕ сортируем - берем в порядке колонок в таблице
        
        # Собираем все активности с их временами
        activities = []
        for time_col in time_columns:
            activity = person_row.get(time_col)
            if pd.notna(activity) and str(activity).strip():
                activities.append({
                    'time': time_col,
                    'activity': str(activity).strip()
                })
        
        # Группируем соседние одинаковые активности
        if not activities:
            return schedule
        current_start = activities[0]['time']
        current_activity = activities[0]['activity']
        
        for i in range(1, len(activities)):
            if activities[i]['activity'] != current_activity:
                # Добавляем завершенную активность
                schedule.append({
                    'start': self._format_time(current_start),
                    'end': self._format_time(activities[i]['time']),
                    'activity': current_activity
                })
                
                # Начинаем новую активность
                current_start = activities[i]['time']
                current_activity = activities[i]['activity']
        
        # Добавляем последнюю активность
        schedule.append({
            'start': self._format_time(current_start),
            'end': 'До конца',
            'activity': current_activity
        })
        
        return schedule
    
    def _time_to_minutes(self, time_obj) -> int:
        """Конвертация времени в минуты для сортировки"""
        if isinstance(time_obj, time):
            return time_obj.hour * 60 + time_obj.minute
        elif isinstance(time_obj, str) and ':' in time_obj:
            try:
                h, m = map(int, time_obj.split(':')[:2])
                return h * 60 + m
            except:
                return 0
        return 0
    
    def _format_time(self, time_obj) -> str:
        """Форматирование времени для вывода"""
        if isinstance(time_obj, time):
            return time_obj.strftime('%H:%M')
        elif isinstance(time_obj, str):
            return time_obj
        return str(time_obj)
    
    def print_schedule(self, person_schedule: Dict) -> str:
        """Красивый вывод расписания"""
        if not person_schedule:
            print("Человек не найден")
            return
        day_names = {
            'четверг': 'четверг',
            'пятница': 'пятница',
            'суббота': 'суббота',
            'воскресенье': 'воскресенье'
        }
        output = {}
        for day in self.days:
            if day not in person_schedule:
                continue
            output[day] = ""
            output[day] += f"{day_names[day]}: \n"

            schedule = person_schedule[day]
            for item in schedule:
                output[day] += f"    {item['start']} - {item['end']}: {item['activity']} \n"
            
            output[day] += "\n"
        return output
    def get(self, search_query: str):
        """Получение расписания сотрудника для бота"""
        if not search_query:
            return "Ошибка: Введите фамилию или фамилию+имя для поиска"
        
        person_data = self.search_person(search_query)
        if person_data:
            # Возвращаем форматированное расписание
            return self.format_schedule_for_bot(person_data)
        else:
            return f"Сотрудник '{search_query}' не найден"
    
    def format_schedule_for_bot(self, person_data: Dict) -> str:
        """Форматирование расписания для бота"""
        if not person_data:
            return "Данные не найдены"
        
        result = f"👤 {person_data['name']}\n"
        result += f"📞 {person_data['phone']}\n"
        result += f"📋 {person_data['position']}\n\n"
        
        day_names = {
            'четверг': '📅 Четверг',
            'пятница': '📅 Пятница', 
            'суббота': '📅 Суббота',
            'воскресенье': '📅 Воскресенье'
        }
        
        for day in self.days:
            if day not in person_data['schedule']:
                continue
                
            result += f"{day_names[day]}:\n"
            
            schedule = person_data['schedule'][day]
            for item in schedule:
                result += f"    {item['start']} - {item['end']}: {item['activity']}\n"
            
            result += "\n"
        
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

def init_scheduler(spreadsheet_url: str = None, credentials_path: str = None):
    """Инициализация планировщика"""
    global scheduler
    scheduler = GridScheduler(
        spreadsheet_url=spreadsheet_url,
        credentials_path=credentials_path
    )
    return scheduler


if __name__ == "__main__":
    scheduler = init_scheduler(
        spreadsheet_url=os.getenv("SPREADSHEET_URL"),
        credentials_path=GRID_CREDENTIALS_PATH
    )
    print(scheduler.get("Будай"))
