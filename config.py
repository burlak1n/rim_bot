"""
Конфигурация rim_bot - централизованное управление константами и настройками
"""

import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# === ФАЙЛЫ И ПУТИ ===
CREDS_FILE = 'credentials.json'
GRID_CREDENTIALS_PATH = "../credentials.json"

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
CALENDAR_URL = os.getenv("CALENDAR_URL")
# BOT_TOKEN = os.getenv("BOT_TOKEN")
# BOT_USERNAME = os.getenv("BOT_USERNAME")
# DATABASE_URL = os.getenv("DATABASE_URL", "rim.db")
# PORT = os.getenv("PORT", "8080")

# === НАСТРОЙКИ КАЛЕНДАРЯ ===
WORKSHEET_NAME = 'календарь new'
CACHE_DURATION_HOURS = 1  # Время жизни кеша в часах

# === СООТВЕТСТВИЕ РУССКИХ МЕСЯЦЕВ ЧИСЛАМ ===
MONTHS = {
    'ЯНВАРЬ': 1, 'ФЕВРАЛЬ': 2, 'МАРТ': 3, 'АПРЕЛЬ': 4, 'МАЙ': 5, 'ИЮНЬ': 6,
    'ИЮЛЬ': 7, 'АВГУСТ': 8, 'СЕНТЯБРЬ': 9, 'ОКТЯБРЬ': 10, 'НОЯБРЬ': 11, 'ДЕКАБРЬ': 12
}

# === НАЗВАНИЯ ДНЕЙ НЕДЕЛИ ===
WEEKDAYS = {
    0: 'понедельник', 1: 'вторник', 2: 'среда', 3: 'четверг', 
    4: 'пятница', 5: 'суббота', 6: 'воскресенье'
}

# === НАЗВАНИЯ МЕСЯЦЕВ В РОДИТЕЛЬНОМ ПАДЕЖЕ ===
MONTH_NAMES = {
    1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
    7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
}

# === НАЗВАНИЯ ДНЕЙ НЕДЕЛИ ДЛЯ ПОИСКА В ЛИСТАХ ===
WEEKDAY_NAMES = [
    'ПОНЕДЕЛЬНИК', 'ВТОРНИК', 'СРЕДА', 'ЧЕТВЕРГ', 'ПЯТНИЦА', 'СУББОТА', 'ВОСКРЕСЕНЬЕ',
    'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'
]

# === НАСТРОЙКИ GRID SCHEDULER ===
DEFAULT_GRID_DAYS = ['четверг', 'пятница', 'суббота', 'воскресенье']

# === ПРОВЕРКИ ОБЯЗАТЕЛЬНЫХ ПЕРЕМЕННЫХ ===
def validate_config():
    """Проверка обязательных переменных конфигурации"""
    errors = []
    
    # Проверяем наличие URL календаря
    if not CALENDAR_URL:
        errors.append(
            "CALENDAR_URL не найден в переменных окружения. "
            "Создайте файл .env в корневой директории проекта и добавьте строку: "
            "CALENDAR_URL=your_google_sheets_url_here"
        )
    
    # Проверяем наличие credentials файла
    if not os.path.exists(CREDS_FILE):
        errors.append(
            f"Файл {CREDS_FILE} не найден. "
            "Скачайте credentials.json из Google Cloud Console и поместите его в папку rim_bot/"
        )
    
    # Выводим все ошибки
    if errors:
        for error in errors:
            raise ValueError(error)

# Проводим проверку при импорте модуля
try:
    validate_config()
except ValueError as e:
    # Переопределяем как предупреждение, чтобы не блокировать импорт
    import warnings
    warnings.warn(str(e), UserWarning)
