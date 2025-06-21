import datetime
import gspread
from collections import defaultdict
import sys
from pathlib import Path

# Добавляем родительскую директорию в sys.path если её нет
current_dir = Path(__file__).parent.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from config import (
    CREDS_FILE, CALENDAR_URL as URL, WORKSHEET_NAME, CACHE_DURATION_HOURS,
    MONTHS, WEEKDAYS, MONTH_NAMES
)

# Кеш для данных
_CACHED_EVENTS = None
_CACHE_TIMESTAMP = None

def parse_calendar_data(data):
    """Парсинг двухмерного массива календаря"""
    events_by_date = defaultdict(list)
    current_year = 2025
    current_month = None
    week_dates = [None] * 7
    
    # Сначала собираем все названия проектов из левого столбца
    all_projects = set()
    for row in data:
        if not row or len(row) < 8:
            continue
        
        project_name = row[0].strip()
        # Пропускаем месяцы, дни недели и пустые строки
        if (project_name and 
            project_name not in MONTHS and 
            project_name not in ['ПОНЕДЕЛЬНИК', 'ВТОРНИК', 'СРЕДА', 'ЧЕТВЕРГ', 'ПЯТНИЦА', 'СУББОТА ', 'ВОСКРЕСЕНЬЕ'] and
            not project_name.isdigit()):
            all_projects.add(project_name)
    
    # Теперь парсим события
    for row_idx, row in enumerate(data):
        if not row or len(row) < 8:
            continue
            
        # Проверка на месяц
        if row[0] in MONTHS:
            current_month = MONTHS[row[0]]
            continue
            
        # Проверка на строку с днями недели (пропускаем)
        if row[1] in ['ПОНЕДЕЛЬНИК', 'ВТОРНИК', 'СРЕДА', 'ЧЕТВЕРГ', 'ПЯТНИЦА', 'СУББОТА ', 'ВОСКРЕСЕНЬЕ']:
            continue
            
        # Проверка на строку с датами
        try:
            # Если во втором элементе число, это строка с датами
            if row[1].isdigit():
                week_dates = []
                for i in range(1, 8):
                    if i < len(row) and row[i].isdigit():
                        week_dates.append(int(row[i]))
                    else:
                        week_dates.append(None)
                continue
        except (AttributeError, ValueError):
            pass
            
        # Обработка строки с событиями
        project_name = row[0].strip()
        if project_name and current_month and week_dates:
            # Обрабатываем каждую ячейку в строке
            for i in range(1, min(8, len(row))):
                day_idx = i - 1
                if week_dates[day_idx] and row[i].strip():
                    event_text = row[i].strip()
                    
                    try:
                        date = datetime.date(current_year, current_month, week_dates[day_idx])
                        
                        # Определяем является ли это комбинацией проектов
                        # Событие является комбинацией если содержит "+" И содержит название другого проекта
                        is_project_combination = False
                        if "+" in event_text:
                            # Проверяем, содержит ли событие название проекта, отличного от текущего
                            for project in all_projects:
                                if (project.lower() in event_text.lower() and 
                                    project.lower() != project_name.lower() and
                                    not any(keyword.lower() in event_text.lower() 
                                           for keyword in ['репетиция', 'собрание', 'концепции'])):
                                    is_project_combination = True
                                    break
                        
                        if is_project_combination:
                            # Комбинация проектов добавляется без префикса проекта
                            event_to_add = event_text
                        else:
                            # Обычное событие с префиксом проекта
                            event_to_add = f"{project_name}: {event_text}"
                        
                        # Добавляем событие только если его еще нет
                        if event_to_add not in events_by_date[date]:
                            events_by_date[date].append(event_to_add)
                        
                        # Проверяем объединенные ячейки - распространяем на все пустые ячейки справа
                        if is_project_combination:
                            # Для комбинаций проектов проверяем все следующие дни в неделе
                            for next_day_offset in range(1, 7 - day_idx):
                                next_day_idx = day_idx + next_day_offset
                                if week_dates[next_day_idx]:
                                    # Проверяем что ячейка пустая
                                    if (next_day_idx + 1 >= len(row) or not row[next_day_idx + 1].strip()):
                                        next_date = datetime.date(current_year, current_month, week_dates[next_day_idx])
                                        if event_to_add not in events_by_date[next_date]:
                                            events_by_date[next_date].append(event_to_add)
                                    else:
                                        # Если встретили непустую ячейку, прекращаем распространение
                                        break
                        
                    except (ValueError, IndexError):
                        continue
                        
    return events_by_date

def format_calendar_output(events_by_date, target_date=None, days_ahead=7, timestamp=None):
    """Форматирование вывода календаря"""
    if target_date is None:
        target_date = datetime.date.today()

    output_lines = []
    
    # Генерируем следующие 7 дней начиная с target_date
    for i in range(days_ahead):
        current_date = target_date + datetime.timedelta(days=i)
        
        # Определяем день недели
        weekday_name = WEEKDAYS[current_date.weekday()].capitalize()
        month_name = MONTH_NAMES[current_date.month]
        
        # Определяем, сегодня ли это
        today_marker = " (сегодня)" if current_date == target_date else ""
        
        # Заголовок дня
        header = f"{weekday_name}, {current_date.day} {month_name}{today_marker}:"
        output_lines.append(header)
        
        # События дня
        if current_date in events_by_date:
            # Сортируем события по алфавиту
            sorted_events = sorted(events_by_date[current_date])
            for event in sorted_events:
                output_lines.append(f"- {event}")
        else:
            output_lines.append("- Событий нет")
        
        output_lines.append("")  # Пустая строка между днями
    if timestamp is not None:
        output_lines.append(f"Календарь обновлен: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
    return "\n".join(output_lines)

def is_cache_valid():
    """Проверка актуальности кеша"""
    global _CACHE_TIMESTAMP
    if _CACHED_EVENTS is None or _CACHE_TIMESTAMP is None:
        return False
    
    now = datetime.datetime.now()
    cache_age = now - _CACHE_TIMESTAMP
    return cache_age.total_seconds() < CACHE_DURATION_HOURS * 3600

def get_events_data(force_refresh=False):
    """Получение данных событий с кешированием"""
    global _CACHED_EVENTS, _CACHE_TIMESTAMP
    
    # Проверяем кеш если не требуется принудительное обновление
    if not force_refresh and is_cache_valid():
        print("Используются кешированные данные")
        return _CACHED_EVENTS, _CACHE_TIMESTAMP
    
    print("Загружаются данные из Google Sheets...")
    # Получаем данные из Google Sheets
    gc = gspread.service_account(filename=CREDS_FILE)
    sh = gc.open_by_url(URL)
    
    # Используем только основной лист
    worksheet = sh.worksheet(WORKSHEET_NAME)
    sheet_data = worksheet.get_all_values()
    events_by_date = parse_calendar_data(sheet_data)
    
    # Обновляем кеш
    _CACHED_EVENTS = events_by_date
    _CACHE_TIMESTAMP = datetime.datetime.now()
    
    return events_by_date, _CACHE_TIMESTAMP

def get(days_ahead: int = 7, force_refresh: bool = False) -> str:
    # Получаем данные (из кеша или Google Sheets)
    events_by_date, timestamp = get_events_data(force_refresh=force_refresh)
    formatted_output = format_calendar_output(events_by_date, days_ahead=days_ahead, timestamp=timestamp)
    return formatted_output

if __name__ == '__main__':
    print(get()) 