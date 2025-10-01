from config import GRID_CREDENTIALS_PATH, DEFAULT_GRID_DAYS, WEEKDAY_NAMES
import gspread
import pandas as pd
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Union
from abc import ABC, abstractmethod
import os
import json
import sys
from pathlib import Path
from enum import Enum

# Добавляем родительскую директорию в sys.path если её нет
current_dir = Path(__file__).parent.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))


# Перечисление для уровней доступа

class AccessLevel(Enum):
    GUEST = "guest"
    USER = "user"
    EMPLOYEE = "employee"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class BaseUser(ABC):
    """
    Абстрактный базовый класс для всех пользователей системы
    """

    def __init__(self, user_id: str, name: str, access_level: AccessLevel):
        self._user_id = user_id
        self._name = name
        self._access_level = access_level
        self._last_login = None
        self._login_count = 0

    @abstractmethod
    def can_view_schedule(self, target_user: str = None) -> bool:
        """Может ли пользователь просматривать расписание"""
        pass

    @abstractmethod
    def can_modify_schedule(self) -> bool:
        """Может ли пользователь изменять расписание"""
        pass

    @abstractmethod
    def get_available_actions(self) -> List[str]:
        """Получить список доступных действий для пользователя"""
        pass

    def format_greeting(self) -> str:
        """Приветствие пользователя (может быть переопределено в наследниках)"""
        return f"Привет, {self._name}!"

    def format_user_info(self) -> str:
        """Форматирование информации о пользователе (может быть переопределено)"""
        return f"Пользователь: {self._name} (ID: {self._user_id})"

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def access_level(self) -> AccessLevel:
        return self._access_level

    @property
    def last_login(self) -> Optional[datetime]:
        return self._last_login

    @property
    def login_count(self) -> int:
        return self._login_count

    # Общие методы для всех пользователей
    def login(self):
        """Метод входа в систему"""
        self._last_login = datetime.now()
        self._login_count += 1
        print(
            f"Пользователь {self._name} вошел в систему (заходов: {self._login_count})")


class GuestUser(BaseUser):
    """
    Гость системы - только базовый просмотр публичной информации
    """

    def __init__(self, user_id: str, name: str):
        super().__init__(user_id, name, AccessLevel.GUEST)
        self._view_restrictions = ["no_personal_data", "no_schedule_details"]

    def can_view_schedule(self, target_user: str = None) -> bool:
        # Гость может видеть только общедоступную информацию
        return False

    def can_modify_schedule(self) -> bool:
        return False

    def get_available_actions(self) -> List[str]:
        return ["view_public_info", "view_contacts"]

    def format_greeting(self) -> str:
        return f"Добро пожаловать, гость {self._name}! У вас ограниченный доступ."

    def format_user_info(self) -> str:
        return f"Гость: {self._name} (ограниченный доступ)"


class RegularUser(BaseUser):
    """Зарегистрированный пользователь - может просматривать свое расписание

    Расширяет функциональность BaseUser для авторизованных пользователей.
    """

    def __init__(self, user_id: str, name: str, email: str = ""):
        super().__init__(user_id, name, AccessLevel.USER)
        self._email = email  # Дополнительная инкапсуляция
        self._favorites = []  # Избранные контакты/события

    def can_view_schedule(self, target_user: str = None) -> bool:
        # Может просматривать только свое расписание
        return target_user is None or target_user == self._user_id

    def can_modify_schedule(self) -> bool:
        return False

    def get_available_actions(self) -> List[str]:
        return ["view_own_schedule", "view_contacts", "manage_favorites"]

    def add_to_favorites(self, item: str):
        """Добавление в избранное"""
        if item not in self._favorites:
            self._favorites.append(item)

    @property
    def email(self) -> str:
        return self._email


class EmployeeUser(BaseUser):
    """Сотрудник - может просматривать расписания коллег

    Расширяет возможности для внутренних пользователей организации.
    """

    def __init__(self, user_id: str, name: str, department: str = "", position: str = ""):
        super().__init__(user_id, name, AccessLevel.EMPLOYEE)
        self._department = department
        self._position = position
        self._colleagues = []  # Список коллег

    def can_view_schedule(self, target_user: str = None) -> bool:
        # Может просматривать расписания в рамках организации
        return True

    def can_modify_schedule(self) -> bool:
        return False

    def get_available_actions(self) -> List[str]:
        return ["view_any_schedule", "view_contacts", "search_colleagues",
                "view_department_info"]

    # ПОЛИМОРФИЗМ: Специализированное приветствие
    def format_greeting(self) -> str:
        dept_info = f" ({self._department})" if self._department else ""
        return f"Привет, сотрудник {self._name}{dept_info}!"

    def format_user_info(self) -> str:
        return f"Сотрудник: {self._name}, {self._position} ({self._department})"

    def add_colleague(self, colleague_id: str):
        """Добавление коллеги в список"""
        if colleague_id not in self._colleagues:
            self._colleagues.append(colleague_id)

    @property
    def department(self) -> str:
        return self._department

    @property
    def position(self) -> str:
        return self._position


class AdminUser(BaseUser):
    """Администратор - полный доступ к системе и управлению

    Максимальный набор прав и возможностей в системе.
    """

    def __init__(self, user_id: str, name: str, admin_level: str = "basic"):
        super().__init__(user_id, name, AccessLevel.ADMIN)
        self._admin_level = admin_level  # basic, advanced, super
        self._managed_users = []
        self._system_actions_log = []

    def can_view_schedule(self, target_user: str = None) -> bool:
        return True

    def can_modify_schedule(self) -> bool:
        return True

    def get_available_actions(self) -> List[str]:
        actions = ["view_any_schedule", "modify_schedule", "manage_users",
                   "view_analytics", "system_settings"]

        if self._admin_level == "super":
            actions.extend(
                ["database_access", "system_backup", "user_management"])

        return actions

    def format_greeting(self) -> str:
        level_text = f" ({self._admin_level} уровень)" if self._admin_level != "basic" else ""
        return f"Добро пожаловать, администратор {self._name}{level_text}! Полный доступ активен."

    def format_user_info(self) -> str:
        return f"Администратор: {self._name} (уровень: {self._admin_level})"

    def add_managed_user(self, user_id: str):
        """Добавление пользователя под управление"""
        if user_id not in self._managed_users:
            self._managed_users.append(user_id)

    def log_system_action(self, action: str):
        """Логирование системных действий"""
        log_entry = {
            "timestamp": datetime.now(),
            "admin": self._name,
            "action": action
        }
        self._system_actions_log.append(log_entry)

    @property
    def admin_level(self) -> str:
        return self._admin_level


class GridScheduler:
    """
    Основной класс для работы с расписанием с интегрированной системой пользователей
    """

    def __init__(self, spreadsheet_url: str = None, credentials_path: str = None):
        self._spreadsheet_url = spreadsheet_url
        self._credentials_path = self._resolve_credentials_path(
            credentials_path)
        self._gc = None
        self._spreadsheet = None
        self._days = DEFAULT_GRID_DAYS.copy()
        self._weekday_names = WEEKDAY_NAMES

        # Система пользователей
        self._current_user: Optional[BaseUser] = None
        self._users_registry: Dict[str, BaseUser] = {}
        self._session_log = []

        # Автоматическое подключение при инициализации
        self._initialize_connection()

    def _resolve_credentials_path(self, credentials_path: str) -> str:
        """Приватный метод определения пути к credentials файлу"""
        if credentials_path and os.path.isabs(credentials_path):
            return credentials_path
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(script_dir, credentials_path or "../credentials.json")

    def _initialize_connection(self):
        """Приватный метод инициализации подключения"""
        if self._spreadsheet_url and os.path.exists(self._credentials_path):
            if self.connect():
                self._days = self._get_days_from_sheets()

    # ПОЛИМОРФИЗМ: Фабричный метод для создания пользователей разных типов
    def create_user(self, user_type: str, user_id: str, name: str, **kwargs) -> BaseUser:
        """Фабричный метод создания пользователей

        Демонстрирует полиморфизм через создание объектов разных классов
        с единым интерфейсом.
        """

        user_factories = {
            "guest": lambda: GuestUser(user_id, name),
            "user": lambda: RegularUser(user_id, name, kwargs.get("email", "")),
            "employee": lambda: EmployeeUser(user_id, name,
                                             kwargs.get("department", ""),
                                             kwargs.get("position", "")),
            "admin": lambda: AdminUser(user_id, name, kwargs.get("admin_level", "basic"))
        }

        if user_type not in user_factories:
            raise ValueError(f"Неизвестный тип пользователя: {user_type}")

        user = user_factories[user_type]()
        self._users_registry[user_id] = user

        # Логируем создание пользователя
        self._log_action(f"Создан пользователь: {user.format_user_info()}")

        return user

    def authenticate_user(self, user_id: str) -> bool:
        """Аутентификация пользователя в системе"""
        if user_id in self._users_registry:
            self._current_user = self._users_registry[user_id]
            self._current_user.login()
            self._log_action(f"Вход пользователя: {self._current_user.name}")
            return True
        return False

    def logout(self):
        """Выход пользователя из системы"""
        if self._current_user:
            self._log_action(f"Выход пользователя: {self._current_user.name}")
            print(f"Пользователь {self._current_user.name} вышел из системы")
            self._current_user = None

    # ПОЛИМОРФИЗМ в действии: метод работает по-разному для разных типов пользователей
    def get_schedule(self, search_query: str, target_user: str = None) -> str:
        """Получение расписания с проверкой прав доступа

        Демонстрирует полиморфизм: один метод работает по-разному
        в зависимости от типа текущего пользователя.
        """

        if not self._current_user:
            return "❌ Ошибка: Необходимо войти в систему"

        if not self._current_user.can_view_schedule(target_user):
            actions_list = ", ".join(
                self._current_user.get_available_actions())
            return f"❌ Нет прав для просмотра расписания.\\n📋 Доступные действия: {actions_list}\\n\\n{self._current_user.format_greeting()}"

        result = self._search_schedule_internal(search_query)

        # Добавляем персонализированную информацию
        greeting = self._current_user.format_greeting()
        user_info = self._current_user.format_user_info()

        self._log_action(f"Просмотр расписания: {search_query}")

        return f"{greeting}\\n{user_info}\\n\\n📅 {result}"

    def modify_schedule(self, modifications: Dict) -> str:
        """Изменение расписания с проверкой административных прав"""

        if not self._current_user:
            return "❌ Ошибка: Необходимо войти в систему"

        # ПОЛИМОРФНАЯ ПРОВЕРКА: только администраторы могут изменять
        if not self._current_user.can_modify_schedule():
            available_actions = ", ".join(
                self._current_user.get_available_actions())
            return f"❌ Нет прав для изменения расписания.\\n📋 Доступные действия: {available_actions}"

        # Логируем административное действие
        if isinstance(self._current_user, AdminUser):
            self._current_user.log_system_action(
                f"Изменение расписания: {modifications}")

        self._log_action(f"Изменение расписания: {modifications}")

        return "✅ Расписание успешно изменено"

    def get_user_menu(self) -> str:
        """Получение персонализированного меню пользователя

        """

        if not self._current_user:
            return "❌ Войдите в систему для получения меню"

        # ПОЛИМОРФИЗМ: каждый тип пользователя имеет свой набор действий
        actions = self._current_user.get_available_actions()
        greeting = self._current_user.format_greeting()
        user_info = self._current_user.format_user_info()

        menu = f"{greeting}\\n{user_info}\\n\\n📋 Доступные действия:\\n"

        for i, action in enumerate(actions, 1):
            menu += f"{i}. {action}\\n"

        # Добавляем статистику для администраторов
        if isinstance(self._current_user, AdminUser):
            menu += f"\\n👥 Пользователей в системе: {len(self._users_registry)}"
            menu += f"\\n📊 Заходов в систему: {self._current_user.login_count}"

        return menu

    def get_system_stats(self) -> str:
        """Получение статистики системы (только для администраторов)"""

        if not self._current_user or not isinstance(self._current_user, AdminUser):
            return "❌ Доступно только администраторам"

        stats = f"📊 СТАТИСТИКА СИСТЕМЫ\\n"
        stats += f"👥 Всего пользователей: {len(self._users_registry)}\\n"

        # Подсчет пользователей по типам
        user_types = {}
        for user in self._users_registry.values():
            user_type = type(user).__name__
            user_types[user_type] = user_types.get(user_type, 0) + 1

        for user_type, count in user_types.items():
            stats += f"   - {user_type}: {count}\\n"

        stats += f"📝 Записей в логе: {len(self._session_log)}\\n"

        if self._current_user.admin_level == "super":
            stats += f"\\n🔧 Уровень доступа: Супер-администратор"

        return stats

    # Приватные методы (ИНКАПСУЛЯЦИЯ)
    def _log_action(self, action: str):
        """Приватный метод логирования действий"""
        log_entry = {
            "timestamp": datetime.now(),
            "user": self._current_user.name if self._current_user else "System",
            "action": action
        }
        self._session_log.append(log_entry)

    def _search_schedule_internal(self, search_query: str) -> str:
        """Приватный метод поиска расписания"""
        return f"Результаты поиска для '{search_query}'"

    # Оригинальные методы GridScheduler (адаптированные)
    def connect(self) -> bool:
        """Подключение к Google Sheets"""
        if not self._spreadsheet_url:
            return False

        try:
            if os.path.exists(self._credentials_path):
                self._gc = gspread.service_account(
                    filename=self._credentials_path)
            else:
                self._gc = gspread.service_account()

            self._spreadsheet = self._gc.open_by_url(self._spreadsheet_url)
            print(
                f"✅ Успешно подключились к Google Sheets {self._spreadsheet.title}")
            return True

        except Exception as e:
            print(f"❌ Ошибка подключения к Google Sheets: {e}")
            return False

    def _get_days_from_sheets(self) -> List[str]:
        """Приватный метод получения дней недели из листов"""
        if not self._spreadsheet:
            return self._days

        try:
            all_worksheets = self._spreadsheet.worksheets()
            found_days = []

            for worksheet in all_worksheets:
                worksheet_name = worksheet.title.lower()
                for day in self._weekday_names:
                    if day in worksheet_name:
                        found_days.append(day)
                        break

            unique_days = []
            for day in self._weekday_names:
                if day in found_days and day not in unique_days:
                    unique_days.append(day)

            return unique_days if unique_days else self._days

        except Exception as e:
            print(f"❌ Ошибка получения дней из листов: {e}")
            return self._days

    @property
    def current_user(self) -> Optional[BaseUser]:
        return self._current_user

    @property
    def users_count(self) -> int:
        return len(self._users_registry)


# Глобальные переменные для совместимости с оригинальным кодом
scheduler = None
spreadsheet_url = None
credentials_path = GRID_CREDENTIALS_PATH


def init_scheduler(spreadsheet_url: str = None, credentials_path: str = None):
    """Инициализация планировщика (совместимость с оригинальным API)"""
    global scheduler
    scheduler = GridScheduler(
        spreadsheet_url=spreadsheet_url,
        credentials_path=credentials_path
    )
    return scheduler


if __name__ == "__main__":
    # Демонстрация принципов ООП
    demonstrate_oop_features()
