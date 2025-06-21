import sys
import os
from pathlib import Path
from dotenv import load_dotenv

from config import CREDS_FILE, GRID_CREDENTIALS_PATH

# Добавляем родительскую директорию в sys.path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

# Загружаем переменные окружения
load_dotenv()

def main():
    # Импортируем модули после настройки sys.path
    from calendar_events import get as get_calendar
    from grid import init_scheduler
    
    print("=== Запуск rim_bot ===")
    print("Получение календаря...")
    calendar_data = get_calendar(days_ahead=7, force_refresh=False)
    print(calendar_data)
    
    print("\nИнициализация планировщика...")
    print(os.getenv("SPREADSHEET_URL"))
    scheduler = init_scheduler(
        spreadsheet_url=os.getenv("SPREADSHEET_URL"),
        credentials_path=GRID_CREDENTIALS_PATH
    )
    
    print("Поиск 'Будай'...")
    result = scheduler.get("Будай")
    print(result)

if __name__ == '__main__':
    main() 