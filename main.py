import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import ADMINS, BOT_TOKEN
from user import user

db = None  # Место для инициализации базы данных
# scheduler = None  # Место для инициализации планировщика задач
admins = [int(admin_id) for admin_id in ADMINS]

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token = BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.include_router(user)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())