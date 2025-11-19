import os
import sys

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, CallbackQuery, Message

from config import ADMINS, GRID_CREDENTIALS_PATH, SPREADSHEET_URL
from grid import GridScheduler, init_scheduler
from keyboards.user import update_schedule_admin_kb, update_schedule_kb

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

user = Router()
scheduler: GridScheduler = init_scheduler(
    spreadsheet_url=SPREADSHEET_URL, credentials_path=GRID_CREDENTIALS_PATH
)
admins = [int(admin_id) for admin_id in ADMINS]


@user.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Добро пожаловать в в бота сетку-хуетку \nЧтобы я работал, напиши мне свою фамилию / фамилию + имя"
    )


@user.message(Command(BotCommand(command="phones", description="Важные номера")))
async def phones_cmd(message: Message):
    await message.answer(scheduler.format_important_numbers_for_bot())


@user.message()
async def text_surname_cmd(message: Message):
    try:
        data = scheduler.get(message.text.strip())

        if "Сотрудник" not in data:
            # Админам показываем расширенную клавиатуру
            keyboard = (
                update_schedule_admin_kb
                if message.from_user.id in admins
                else update_schedule_kb
            )
            await message.answer(data, reply_markup=keyboard)
        else:
            await message.answer(data)

    except AttributeError:
        await message.answer("Неправильный ввод данных")


@user.callback_query(lambda c: c.data == "upd_schedule")
async def process_updating_schedule(callback_query: CallbackQuery):
    name = callback_query.message.text.split("\n")[0][1:].strip()

    try:
        # Просто пересчитываем с текущим временем, БЕЗ обновления кэша
        keyboard = (
            update_schedule_admin_kb
            if callback_query.from_user.id in admins
            else update_schedule_kb
        )
        await callback_query.message.edit_text(
            scheduler.get(name), reply_markup=keyboard
        )
        await callback_query.answer("Расписание обновлено", cache_time=10)

    except TelegramBadRequest:
        await callback_query.answer("Расписание не изменилось!", show_alert=True)

    except Exception as er:
        await callback_query.answer("Ошибка :( ", show_alert=True)
        print(er)


@user.callback_query(lambda c: c.data == "refresh_cache")
async def process_refresh_cache(callback_query: CallbackQuery):
    # Проверка, что пользователь админ
    if callback_query.from_user.id not in admins:
        await callback_query.answer("Доступ запрещен", show_alert=True)
        return

    name = callback_query.message.text.split("\n")[0][1:].strip()

    try:
        await callback_query.answer(
            "Обновляю кэш из Google Sheets...", show_alert=False
        )
        # Обновляем кэш и получаем свежие данные
        await callback_query.message.edit_text(
            scheduler.get(name, force_refresh=True),
            reply_markup=update_schedule_admin_kb,
        )
        await callback_query.answer("Кэш обновлён!", show_alert=True)

    except Exception as er:
        await callback_query.answer("Ошибка обновления кэша :( ", show_alert=True)
        print(er)
