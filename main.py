from __future__ import annotations

import asyncio
import logging
import os
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from api_client import MosSportClient
from config import TELEGRAM_BOT_TOKEN
from handlers import setup_handlers
from monitor import SlotMonitor
from storage import Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def health_handler(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def run_health_server() -> None:
    port = int(os.getenv("PORT", "8080"))
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health server listening on port %s", port)


async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Укажите TELEGRAM_BOT_TOKEN в переменных окружения или .env")
        sys.exit(1)

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    storage = Storage()
    api = MosSportClient()
    monitor = SlotMonitor(bot, storage, api)

    setup_handlers(dp, storage, api, monitor)

    logger.info("Бот запущен. Подписчиков: %s", len(storage.subscribers))

    try:
        await asyncio.gather(
            run_health_server(),
            dp.start_polling(bot),
            monitor.run_forever(),
        )
    finally:
        await api.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
