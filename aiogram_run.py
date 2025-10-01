import asyncio

from create_bot import bot, dp, scheduler
from bot.handlers.user import user

async def main():

    dp.include_router(user)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

