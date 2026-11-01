import os
import time
import hmac
import hashlib
import secrets
from pathlib import Path
from urllib.parse import parse_qsl, quote_plus

import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application


BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_BASE_URL = os.environ["WEBHOOK_BASE_URL"].rstrip("/")
WEBHOOK_PATH = "/telegram-webhook"
WEBHOOK_URL = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
WEB_SERVER_PORT = int(os.getenv("PORT", "10000"))

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_FILE = BASE_DIR / "static" / "index.html"

# This is the players.id value of the existing super-admin account.
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "1"))

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    required = ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError("Missing database environment variables: " + ", ".join(missing))
    DATABASE_URL = (
        f"postgresql://{quote_plus(os.environ['PGUSER'])}:"
        f"{quote_plus(os.environ['PGPASSWORD'])}@{os.environ['PGHOST']}:"
        f"{os.environ['PGPORT'] or '5432'}/{os.environ['PGDATABASE']}"
    )

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db_pool = None


def json_error(message: str, status: int = 400):
    return web.json_response({"ok": False, "error": message}, status=status)


def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="ورود به بازی",
            web_app=WebAppInfo(url=f"{WEBHOOK_BASE_URL}/app")
        )]
    ])
    return keyboard


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "به بازی Dance of Dragons خوش آمدی. برای ورود به بازی روی دکمه زیر بزن.",
        reply_markup=main_menu()
    )


def validate_telegram_init_data(init_data: str):
    if not init_data:
        return None

    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", None)
        if not received_hash:
            return None

        auth_date = int(pairs.get("auth_date", "0"))
        now = int(time.time())
        if auth_date <= 0 or now - auth_date > 300 or auth_date > now + 30:
            return None

        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(pairs.items())
        )
        secret_key = hmac.new(
            b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
        ).digest()
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        import json
        user = json.loads(pairs.get("user", "{}"))
        telegram_id = int(user.get("id", 0))
        if telegram_id <= 0:
            return None
        return telegram_id, auth_date
    except (ValueError, TypeError, KeyError):
        return None


def hash_session_token(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def get_bearer_token(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[7:].strip() or None


async def get_authenticated_player(request):
    token = get_bearer_token(request)
    if not token:
        return None
    token_hash = hash_session_token(token)
    async with request.app["db"].acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT p.id, p.username, p.telegram_id, p.role, p.house_id,
                   p.is_active, p.is_super_admin
            FROM player_sessions s
            JOIN players p ON p.id = s.player_id
            WHERE s.session_token_hash = $1
              AND s.revoked_at IS NULL
              AND s.expires_at > NOW()
            """,
            token_hash,
        )
    return dict(row) if row else None


async def require_super_admin(request):
    player = await get_authenticated_player(request)
    if not player:
        return None, json_error("unauthorized", 401)
    if (
        not player["is_active"]
        or player["role"] != "admin"
        or not player["is_super_admin"]
        or int(player["id"]) != SUPER_ADMIN_ID
    ):
        return None, json_error("forbidden", 403)
    return player, None


async def auth_handler(request):
    try:
        data = await request.json()
    except Exception:
        return json_error("invalid_json")

    init_data = data.get("init_data", "")
    validated = validate_telegram_init_data(init_data)
    if not validated:
        return json_error("telegram_auth_failed", 401)

    telegram_id, auth_date = validated
    async with request.app["db"].acquire() as conn:
        player = await conn.fetchrow(
            """
            SELECT id, username, telegram_id, role, house_id,
                   is_active, is_super_admin
            FROM players
            WHERE telegram_id = $1
            """,
            telegram_id,
        )

        if not player:
            return json_error("account_not_found", 404)
        if not player["is_active"]:
            return json_error("account_disabled", 403)

        await conn.execute(
            "UPDATE players SET telegram_auth_date = $1 WHERE id = $2",
            auth_date, player["id"]
        )

        token = secrets.token_urlsafe(48)
        token_hash = hash_session_token(token)
        await conn.execute(
            """
            INSERT INTO player_sessions
                (player_id, session_token_hash, created_at, expires_at, revoked_at)
            VALUES ($1, $2, NOW(), NOW() + INTERVAL '7 days', NULL)
            """,
            player["id"], token_hash
        )

    return web.json_response({
        "ok": True,
        "token": token,
        "player": {
            "id": player["id"],
            "username": player["username"],
            "telegram_id": player["telegram_id"],
            "role": player["role"],
            "house_id": player["house_id"],
            "is_active": player["is_active"],
            "is_super_admin": player["is_super_admin"],
        }
    })


async def me_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    return web.json_response({"ok": True, "player": player})


async def logout_handler(request):
    token = get_bearer_token(request)
    if token:
        async with request.app["db"].acquire() as conn:
            await conn.execute(
                """
                UPDATE player_sessions
                SET revoked_at = NOW()
                WHERE session_token_hash = $1 AND revoked_at IS NULL
                """,
                hash_session_token(token),
            )
    return web.json_response({"ok": True})


async def admin_players_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error

    try:
        page = max(1, int(request.query.get("page", "1")))
        per_page = min(50, max(1, int(request.query.get("limit", "20"))))
    except ValueError:
        return json_error("invalid_pagination")

    search = request.query.get("search", "").strip()
    offset = (page - 1) * per_page

    async with request.app["db"].acquire() as conn:
        if search:
            pattern = f"%{search}%"
            total = await conn.fetchval(
                """
                SELECT COUNT(*) FROM players
                WHERE username ILIKE $1
                   OR telegram_id::text ILIKE $1
                   OR id::text ILIKE $1
                """,
                pattern,
            )
            rows = await conn.fetch(
                """
                SELECT id, username, telegram_id, role, house_id,
                       is_active, is_super_admin
                FROM players
                WHERE username ILIKE $1
                   OR telegram_id::text ILIKE $1
                   OR id::text ILIKE $1
                ORDER BY id DESC
                LIMIT $2 OFFSET $3
                """,
                pattern, per_page, offset,
            )
        else:
            total = await conn.fetchval("SELECT COUNT(*) FROM players")
            rows = await conn.fetch(
                """
                SELECT id, username, telegram_id, role, house_id,
                       is_active, is_super_admin
                FROM players
                ORDER BY id DESC
                LIMIT $1 OFFSET $2
                """,
                per_page, offset,
            )

    pages = max(1, (total + per_page - 1) // per_page)
    return web.json_response({
        "ok": True,
        "players": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
    })


async def admin_add_player_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error

    try:
        data = await request.json()
    except Exception:
        return json_error("invalid_json")

    raw_id = str(data.get("telegram_id", "")).strip()
    username = str(data.get("username", "")).strip()

    if not raw_id.isdigit():
        return json_error("invalid_telegram_id")
    telegram_id = int(raw_id)
    if telegram_id <= 0 or telegram_id > 9223372036854775807:
        return json_error("invalid_telegram_id")
    if not username or len(username) > 60:
        return json_error("invalid_username")

    try:
        async with request.app["db"].acquire() as conn:
            async with conn.transaction():
                # Serializes additions through this endpoint.
                await conn.execute("SELECT pg_advisory_xact_lock(739201847)")
                existing = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM players WHERE telegram_id = $1)",
                    telegram_id,
                )
                if existing:
                    return json_error("telegram_id_exists", 409)

                player = await conn.fetchrow(
                    """
                    INSERT INTO players
                        (username, password_hash, telegram_id, role, house_id,
                         is_active, created_at, is_super_admin)
                    VALUES ($1, NULL, $2, 'player', NULL, TRUE, NOW(), FALSE)
                    RETURNING id, username, telegram_id, role, house_id,
                              is_active, is_super_admin
                    """,
                    username, telegram_id,
                )
        return web.json_response({"ok": True, "player": dict(player)}, status=201)
    except asyncpg.UniqueViolationError:
        return json_error("telegram_id_exists", 409)


async def index_handler(request):
    return web.FileResponse(WEBAPP_FILE)


async def on_startup(app):
    global db_pool
    app["db"] = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5,
        ssl="require",
    )
    db_pool = app["db"]
    await bot.set_webhook(WEBHOOK_URL)


async def on_cleanup(app):
    global db_pool
    if app.get("db"):
        await app["db"].close()
    db_pool = None
    await bot.session.close()


def create_app():
    app = web.Application(client_max_size=1024 * 1024)

    app.router.add_get("/", index_handler)
    app.router.add_get("/app", index_handler)

    app.router.add_post("/api/auth/telegram", auth_handler)
    app.router.add_get("/api/me", me_handler)
    app.router.add_post("/api/logout", logout_handler)
    app.router.add_get("/api/admin/players", admin_players_handler)
    app.router.add_post("/api/admin/players", admin_add_player_handler)

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=WEB_SERVER_PORT)
