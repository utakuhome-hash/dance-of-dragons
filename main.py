import os
import asyncio
import asyncpg

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_BASE_URL = os.environ["WEBHOOK_BASE_URL"].rstrip("/")
WEBHOOK_PATH = "/telegram-webhook"

WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", "10000"))

db_pool = None

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "به دنیای Dance of Dragons خوش آمدی! 🐉\n"
        "بازی در حال آماده‌سازی است."
    )


async def on_startup(app: web.Application):
    print("STARTUP: on_startup has started", flush=True)
    global db_pool

    db_pool = await asyncpg.create_pool(
        host=os.environ["PGHOST"],
        database=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        ssl="require",
        min_size=1,
        max_size=3,
    )

        async with db_pool.acquire() as connection:
        result = await connection.fetchval("SELECT 1")
        print(f"DATABASE CHECK: {result}", flush=True)

    print(f"Database connection successful: {result}", flush=True)

    await bot.set_webhook(
        url=f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
    )

async def on_shutdown(app: web.Application):
    if db_pool:
        await db_pool.close()

    await bot.session.close()


async def main():
    app = web.Application()

    app.router.add_get(
        "/",
        lambda request: web.Response(text="Bot is running")
    )

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
