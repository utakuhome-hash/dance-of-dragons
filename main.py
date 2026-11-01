
import os
import asyncio
import asyncpg
import hashlib
import hmac
import json
import secrets
import time

from pathlib import Path
from urllib.parse import parse_qsl

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


# ==========================================
# CONFIGURATION
# ==========================================

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


# ==========================================
# TELEGRAM BOT MENU
# ==========================================

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


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "به دنیای Dance of Dragons خوش آمدی! 🐉\n\n"
        "جنگ خاندان‌ها، سیاست و سرنوشت وستروس در انتظار توست.\n\n"
        "برای ورود به بازی از دکمهٔ زیر استفاده کن:",
        reply_markup=main_menu()
    )


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


# ==========================================
# TELEGRAM MINI APP AUTHENTICATION
# ==========================================

def validate_telegram_init_data(init_data: str):
    """
    Validate Telegram Mini App initData.
    Returns (telegram_id, auth_date) if valid.
    Otherwise returns None.
    """

    if not init_data or not isinstance(init_data, str):
        return None

    try:
        parsed_items = parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True
        )

        # Reject duplicate fields
        if len(dict(parsed_items)) != len(parsed_items):
            return None

        data = dict(parsed_items)

        received_hash = data.pop("hash", None)

        if not received_hash:
            return None

        auth_date = int(data.get("auth_date", "0"))
        current_time = int(time.time())

        # Reject future or expired authentication data
        if auth_date > current_time + 30:
            return None

        if current_time - auth_date > 300:
            return None

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(data.items())
        )

        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode("utf-8"),
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(
            calculated_hash,
            received_hash
        ):
            return None

        user_json = data.get("user")

        if not user_json:
            return None

        user_data = json.loads(user_json)

        telegram_id = int(user_data["id"])

        if telegram_id <= 0:
            return None

        return telegram_id, auth_date

    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError
    ):
        return None


async def telegram_auth_handler(request: web.Request):
    """
    Authenticate Telegram Mini App user
    and create a server-side session.
    """

    if db_pool is None:
        return web.json_response(
            {
                "ok": False,
                "error": "database_unavailable"
            },
            status=503
        )

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        return web.json_response(
            {
                "ok": False,
                "error": "invalid_request"
            },
            status=400
        )

    if not isinstance(body, dict):
        return web.json_response(
            {
                "ok": False,
                "error": "invalid_request"
            },
            status=400
        )

    init_data = body.get("initData", "")

    auth_result = validate_telegram_init_data(init_data)

    if not auth_result:
        return web.json_response(
            {
                "ok": False,
                "error": "invalid_telegram_auth"
            },
            status=401
        )

    telegram_id, auth_date = auth_result

    try:
        async with db_pool.acquire() as connection:

            player = await connection.fetchrow(
                """
                SELECT
                    id,
                    username,
                    role,
                    house_id,
                    is_active
                FROM players
                WHERE telegram_id = $1
                """,
                telegram_id
            )

            # No automatic account creation
            if not player:
                return web.json_response(
                    {
                        "ok": False,
                        "error": "account_not_found"
                    },
                    status=403
                )

            if not player["is_active"]:
                return web.json_response(
                    {
                        "ok": False,
                        "error": "account_disabled"
                    },
                    status=403
                )

            # Create a random session token.
            # Only its SHA-256 hash is stored in the database.
            session_token = secrets.token_urlsafe(32)

            session_hash = hashlib.sha256(
                session_token.encode("utf-8")
            ).hexdigest()

            async with connection.transaction():

                await connection.execute(
                    """
                    UPDATE players
                    SET telegram_auth_date = $1
                    WHERE id = $2
                    """,
                    auth_date,
                    player["id"]
                )

                await connection.execute(
                    """
                    INSERT INTO player_sessions (
                        player_id,
                        session_token_hash,
                        created_at,
                        expires_at
                    )
                    VALUES (
                        $1,
                        $2,
                        NOW(),
                        NOW() + INTERVAL '7 days'
                    )
                    """,
                    player["id"],
                    session_hash
                )

        return web.json_response(
            {
                "ok": True,
                "token": session_token,
                "player": {
                    "id": player["id"],
                    "username": player["username"],
                    "role": player["role"],
                    "house_id": player["house_id"]
                }
            }
        )

    except Exception:
        print(
            "Telegram authentication database error",
            flush=True
        )

        return web.json_response(
            {
                "ok": False,
                "error": "authentication_failed"
            },
            status=500
        )


# ==========================================
# APPLICATION STARTUP
# ==========================================

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

    print(
        "Telegram webhook configured",
        flush=True
    )


# ==========================================
# APPLICATION SHUTDOWN
# ==========================================

async def on_shutdown(app: web.Application):
    global db_pool

    if db_pool:
        await db_pool.close()
        db_pool = None

    await bot.session.close()

    print(
        "Application shutdown complete",
        flush=True
    )


# ==========================================
# MAIN WEB APPLICATION
# ==========================================

async def main():
    app = web.Application(
        client_max_size=1024 * 1024
    )

    # Main health check
    app.router.add_get(
        "/",
        lambda request: web.Response(
            text="Bot is running"
        )
    )

    # Telegram Mini App
    app.router.add_get(
        "/app",
        lambda request: web.FileResponse(WEBAPP_FILE)
    )

    # Telegram authentication API
    app.router.add_post(
        "/api/auth/telegram",
        telegram_auth_handler
    )

    # Telegram webhook
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
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
    
