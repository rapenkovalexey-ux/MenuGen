import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database.db import init_db
from handlers import (
    start, settings, menu_generation, menu_edit,
    shopping_list, recipes, subscription, support, tips
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Init DB
    await init_db()

    # Register routers
    dp.include_router(start.router)
    dp.include_router(settings.router)
    dp.include_router(menu_generation.router)
    dp.include_router(menu_edit.router)
    dp.include_router(shopping_list.router)
    dp.include_router(recipes.router)
    dp.include_router(subscription.router)
    dp.include_router(support.router)
    dp.include_router(tips.router)

    logger.info("Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
