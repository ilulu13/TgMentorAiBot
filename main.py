import asyncio
from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from handlers import router
from database import create_db_pool, close_db_pool


async def main():
    await create_db_pool()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    print("Бот запущен...")
    try:
        await dp.start_polling(bot)
    finally:
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(main())