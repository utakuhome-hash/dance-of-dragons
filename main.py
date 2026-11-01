
import os
import asyncio
import asyncpg

from pathlib import Path
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)


# =========================
# CONFIGURATION
# =========================

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_BASE_URL = os.environ["WEBHOOK_BASE_URL"].rstrip("/")
WEBHOOK_PATH = "/telegram-webhook"

WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", "10000"))

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_FILE = BASE_DIR / "static" / "index.html"

db_pool = None

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================
# MAIN MENU
# =========================

def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🐉 ورود به مینی‌اپ",
                    web_app=WebAppInfo(
                        url=f"{WEBHOOK_BASE_URL}/app"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏰 قلمرو من",
                    callback_data="my_realm"
                ),
                InlineKeyboardButton(
                    text="👑 خاندان‌ها",
                    callback_data="houses"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚔️ ارتش",
                    callback_data="army"
                ),
                InlineKeyboardButton(
                    text="🐉 اژدهای من",
                    callback_data="dragon"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗺️ نقشه وستروس",
                    callback_data="map"
                ),
                InlineKeyboardButton(
                    text="💰 اقتصاد",
                    callback_data="economy"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🕊️ پیام‌ها",
                    callback_data="messages"
                ),
                InlineKeyboardButton(
                    text="📜 مأموریت‌ها",
                    callback_data="missions"
                ),
            ],
        ]
    )


# =========================
# START COMMAND
# =========================

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "به دنیای Dance of Dragons خوش آمدی! 🐉\n\n"
        "جنگ خاندان‌ها، سیاست و سرنوشت وستروس در انتظار توست.\n\n"
        "برای ورود به بازی از دکمهٔ زیر استفاده کن:",
        reply_markup=main_menu()
    )


# =========================
# MENU BUTTONS
# =========================

sections = {
    "my_realm": "🏰 قلمرو من",
    "houses": "👑 خاندان‌ها",
    "army": "⚔️ ارتش",
    "dragon": "🐉 اژدهای من",
    "map": "🗺️ نقشه وستروس",
    "economy": "💰 اقتصاد",
    "messages": "🕊️ پیام‌ها",
    "missions": "📜 مأموریت‌ها",
}


@dp.callback_query(F.data.in_(sections.keys()))
async def menu_handler(callback: CallbackQuery):
    section_name = sections[callback.data]

    await callback.answer()

    await callback.message.answer(
        f"{section_name}\n\n"
        "این بخش در حال آماده‌سازی است. 🛠️",
        reply_markup=main_menu()
    )


# =========================
# STARTUP
# =========================

async def on_startup(app: web.Application):
    global db_pool

    print("STARTUP: Starting application", flush=True)

    if not WEBAPP_FILE.is_file():
        raise FileNotFoundError(
            f"Mini app file not found: {WEBAPP_FILE}"
        )

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

    await bot.set_webhook(
        url=f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
    )

    print("Telegram webhook configured", flush=True)


# =========================
# SHUTDOWN
# =========================

async def on_shutdown(app: web.Application):
    global db_pool

    if db_pool:
        await db_pool.close()
        db_pool = None

    await bot.session.close()

    print("Application shutdown complete", flush=True)


# =========================
# WEB SERVER
# =========================

async def main():
    app = web.Application()

    # Main health check
    app.router.add_get(
        "/",
        lambda request: web.Response(
            text="Bot is running"
        )
    )

    # Mini App page
    app.router.add_get(
        "/app",
        lambda request: web.FileResponse(WEBAPP_FILE)
    )

    # Telegram webhook
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    ).register(
        app,
        path=WEBHOOK_PATH
    )

    setup_application(
        app,
        dp,
        bot=bot
    )

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        WEB_SERVER_HOST,
        WEB_SERVER_PORT
    )

    await site.start()

    print(
        f"Webhook server is running on port {WEB_SERVER_PORT}",
        flush=True
    )

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
    
