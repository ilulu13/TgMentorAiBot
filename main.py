import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent

from config import BOT_TOKEN
from handlers import router
from database import create_db_pool, close_db_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    await create_db_pool()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    @dp.errors()
    async def error_handler(event: ErrorEvent):
        logger.error(f"[GLOBAL ERROR] update={event.update} exception={event.exception}", exc_info=event.exception)

    print("Бот запущен...")
    try:
        await dp.start_polling(bot)
    finally:
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(main())