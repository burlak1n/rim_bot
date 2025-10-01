from aiogram import Router, F
from aiogram.filters import CommandStart, Command    
from aiogram.types import Message, BotCommand, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from create_bot import bot

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from grid.grid import GridScheduler
from config import SPREADSHEET_URL, GRID_CREDENTIALS_PATH
from create_bot import scheduler
from keyboards.user_keyaboards import update_schedule_kb
# scheduler = GridScheduler(SPREADSHEET_URL,GRID_CREDENTIALS_PATH )

user = Router()

@user.message(CommandStart())
async def cmd_start(message: Message):

    await message.answer('Привет! Добро пожаловать в в бота сетку-хуетку \nЧтобы я работал, напиши мне свою фамилию / фамилию + имя')


@user.message(Command(BotCommand(command = 'phones', description= "Важные номера")))
async def phones_cmd(message: Message):

    await message.answer(scheduler.format_important_numbers_for_bot())

@user.message()
async def text_surname_cmd(message: Message):
    
    try:
        data = scheduler.get(message.text.strip())
        
        if 'Сотрудник' not in data:

            await message.answer(data, reply_markup=update_schedule_kb)

        else:
            await message.answer(data)

    except AttributeError:
        await message.answer("Неправильный ввод данных")

@user.callback_query(lambda c: c.data == 'upd_schedule')
async def process_updating_schedule(callback_query: CallbackQuery):
    
    name = callback_query.message.text.split('\n')[0][1:].strip()

    try:
        await callback_query.message.edit_text(scheduler.get(name), reply_markup=update_schedule_kb)
        await callback_query.answer('Расписание обновлено', cache_time=10)

    except TelegramBadRequest:
        await callback_query.answer('Расписание не изменилось!', show_alert=True)
        
    except Exception as er:
        await callback_query.answer('Ошибка :( ', show_alert=True)
        print(er)


    # await callback_query.message.edit_caption(callback_query.message.message_id, 'Соси хуйййййй')
    # await bot.send_message(callback_query.from_user.id, 'Соси хуй!')

