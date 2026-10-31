import os
import asyncio

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
WEBHOOK_PATH = "/telegram-webhook"
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", "10000"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "به دنیای Dance of Dragons خوش آمدی! 🐉\n"
        "بازی در حال آماده‌سازی است."
    )


async def on_startup(app: web.Application):
    if WEBHOOK_BASE_URL:
        await bot.set_webhook(
            url=f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
        )


async def on_shutdown(app: web.Application):
    await bot.session.close()


async def main():
    app = web.Application()

    app.router.add_get("/", lambda request: web.Response(text="Bot is running"))

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    ).register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        WEB_SERVER_HOST,
        WEB_SERVER_PORT,
    )
    await site.start()

    print("Webhook server is running")

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
