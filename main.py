
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

ADMIN_SETUP_CODE = os.getenv("ADMIN_SETUP_CODE", "")

WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", "10000"))

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_FILE = BASE_DIR / "static" / "index.html"

SUPER_ADMIN_ID = 1

db_pool = None

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ALLOWED_ROLES = {
    "player",
    "house_leader",
    "treasurer",
    "admin",
}


# ==========================================
# RESPONSE HELPERS
# ==========================================

def json_error(error, status=400):
    return web.json_response(
        {"ok": False, "error": error},
        status=status
    )


def get_bearer_token(request):
    header = request.headers.get("Authorization", "")

    if not header.startswith("Bearer "):
        return None

    token = header[7:].strip()

    if not token or len(token) > 512:
        return None

    return token


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
        "برای ورود به بازی از دکمه زیر استفاده کن:",
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
    await callback.answer()
    await callback.message.answer(
        f"{sections[callback.data]}\n\n"
        "این بخش در حال آماده‌سازی است. 🛠️",
        reply_markup=main_menu()
    )


# ==========================================
# TELEGRAM INIT DATA VALIDATION
# ==========================================

def validate_telegram_init_data(init_data: str):
    if not isinstance(init_data, str) or not init_data:
        return None

    try:
        parsed_items = parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True
        )

        if len(dict(parsed_items)) != len(parsed_items):
            return None

        data = dict(parsed_items)
        received_hash = data.pop("hash", None)

        if not received_hash:
            return None

        auth_date = int(data.get("auth_date", "0"))
        current_time = int(time.time())

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

        user_data = json.loads(data["user"])
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


# ==========================================
# SESSION CREATION
# ==========================================

async def create_player_session(connection, player_id):
    token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

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
        player_id,
        token_hash
    )

    return token


def player_response(player, token):
    return web.json_response({
        "ok": True,
        "token": token,
        "player": {
            "id": player["id"],
            "username": player["username"],
            "role": player["role"],
            "house_id": player["house_id"],
            "is_super_admin": player["is_super_admin"],
        }
    })


# ==========================================
# SESSION AUTHENTICATION
# ==========================================

async def get_authenticated_player(request):
    if db_pool is None:
        return None, json_error(
            "database_unavailable",
            503
        )

    token = get_bearer_token(request)

    if not token:
        return None, json_error(
            "missing_session_token",
            401
        )

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    try:
        async with db_pool.acquire() as connection:
            player = await connection.fetchrow(
                """
                SELECT
                    p.id,
                    p.username,
                    p.role,
                    p.house_id,
                    p.is_active,
                    p.is_super_admin,
                    s.id AS session_id
                FROM player_sessions s
                JOIN players p ON p.id = s.player_id
                WHERE
                    s.session_token_hash = $1
                    AND s.revoked_at IS NULL
                    AND s.expires_at > NOW()
                    AND p.is_active = TRUE
                LIMIT 1
                """,
                token_hash
            )

        if not player:
            return None, json_error(
                "invalid_or_expired_session",
                401
            )

        return player, None

    except Exception:
        print("Session validation failed", flush=True)

        return None, json_error(
            "authentication_failed",
            500
        )


async def require_admin(request):
    player, error = await get_authenticated_player(
        request
    )

    if error:
        return None, error

    if player["role"] != "admin":
        return None, json_error(
            "admin_required",
            403
        )

    return player, None


async def require_super_admin(request):
    player, error = await require_admin(request)

    if error:
        return None, error

    if not player["is_super_admin"]:
        return None, json_error(
            "super_admin_required",
            403
        )

    return player, None


# ==========================================
# ADMIN AUDIT LOG
# ==========================================

async def write_admin_log(
    connection,
    admin_id,
    action,
    target_player_id=None,
    details=None
):
    await connection.execute(
        """
        INSERT INTO admin_audit_logs (
            admin_id,
            action,
            target_player_id,
            details,
            created_at
        )
        VALUES ($1, $2, $3, $4::jsonb, NOW())
        """,
        admin_id,
        action,
        target_player_id,
        json.dumps(details or {})
    )


# ==========================================
# NORMAL TELEGRAM LOGIN
# ==========================================

async def telegram_auth_handler(request):
    if db_pool is None:
        return json_error(
            "database_unavailable",
            503
        )

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        return json_error("invalid_request", 400)

    if not isinstance(body, dict):
        return json_error("invalid_request", 400)

    auth_result = validate_telegram_init_data(
        body.get("initData", "")
    )

    if not auth_result:
        return json_error(
            "invalid_telegram_auth",
            401
        )

    telegram_id, auth_date = auth_result

    try:
        async with db_pool.acquire() as connection:
            async with connection.transaction():

                player = await connection.fetchrow(
                    """
                    SELECT
                        id,
                        username,
                        role,
                        house_id,
                        is_active,
                        is_super_admin
                    FROM players
                    WHERE telegram_id = $1
                    FOR UPDATE
                    """,
                    telegram_id
                )

                if not player:
                    return json_error(
                        "account_not_found",
                        403
                    )

                if not player["is_active"]:
                    return json_error(
                        "account_disabled",
                        403
                    )

                await connection.execute(
                    """
                    UPDATE players
                    SET telegram_auth_date = $1
                    WHERE id = $2
                    """,
                    auth_date,
                    player["id"]
                )

                token = await create_player_session(
                    connection,
                    player["id"]
                )

        return player_response(player, token)

    except Exception:
        print("Telegram login failed", flush=True)

        return json_error(
            "authentication_failed",
            500
        )


# ==========================================
# LOGOUT
# ==========================================

async def logout_handler(request):
    if db_pool is None:
        return json_error(
            "database_unavailable",
            503
        )

    token = get_bearer_token(request)

    if not token:
        return json_error(
            "missing_session_token",
            401
        )

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    try:
        async with db_pool.acquire() as connection:
            await connection.execute(
                """
                UPDATE player_sessions
                SET revoked_at = NOW()
                WHERE
                    session_token_hash = $1
                    AND revoked_at IS NULL
                """,
                token_hash
            )

        return web.json_response({"ok": True})

    except Exception:
        print("Logout failed", flush=True)

        return json_error(
            "logout_failed",
            500
        )


# ==========================================
# FIRST ADMIN BOOTSTRAP
# ==========================================

async def admin_bootstrap_handler(request):
    if db_pool is None:
        return json_error(
            "database_unavailable",
            503
        )

    if len(ADMIN_SETUP_CODE) < 24:
        return json_error(
            "admin_setup_not_configured",
            503
        )

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        return json_error("invalid_request", 400)

    if not isinstance(body, dict):
        return json_error("invalid_request", 400)

    supplied_code = body.get("setupCode", "")
    init_data = body.get("initData", "")

    if not isinstance(supplied_code, str):
        return json_error("invalid_request", 400)

    if not hmac.compare_digest(
        supplied_code.encode("utf-8"),
        ADMIN_SETUP_CODE.encode("utf-8")
    ):
        return json_error(
            "invalid_setup_code",
            403
        )

    auth_result = validate_telegram_init_data(
        init_data
    )

    if not auth_result:
        return json_error(
            "invalid_telegram_auth",
            401
        )

    telegram_id, auth_date = auth_result
    admin_username = f"admin_{telegram_id}"

    try:
        async with db_pool.acquire() as connection:
            async with connection.transaction():

                await connection.execute(
                    "SELECT pg_advisory_xact_lock(739201846)"
                )

                existing_admin = await connection.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM players
                        WHERE role = 'admin'
                    )
                    """
                )

                if existing_admin:
                    return json_error(
                        "admin_already_exists",
                        403
                    )

                existing_player = await connection.fetchrow(
                    """
                    SELECT id
                    FROM players
                    WHERE telegram_id = $1
                    """,
                    telegram_id
                )

                if existing_player:
                    return json_error(
                        "telegram_already_registered",
                        409
                    )

                player = await connection.fetchrow(
                    """
                    INSERT INTO players (
                        username,
                        password_hash,
                        telegram_id,
                        role,
                        house_id,
                        is_active,
                        is_super_admin,
                        created_at,
                        telegram_auth_date
                    )
                    VALUES (
                        $1,
                        NULL,
                        $2,
                        'admin',
                        NULL,
                        TRUE,
                        TRUE,
                        NOW(),
                        $3
                    )
                    RETURNING
                        id,
                        username,
                        role,
                        house_id,
                        is_active,
                        is_super_admin
                    """,
                    admin_username,
                    telegram_id,
                    auth_date
                )

                token = await create_player_session(
                    connection,
                    player["id"]
                )

        return player_response(player, token)

    except asyncpg.UniqueViolationError:
        return json_error(
            "account_conflict",
            409
        )

    except Exception:
        print("Admin bootstrap failed", flush=True)

        return json_error(
            "admin_setup_failed",
            500
        )


# ==========================================
# CURRENT PLAYER PROFILE
# ==========================================

async def me_handler(request):
    player, error = await get_authenticated_player(
        request
    )

    if error:
        return error

    return web.json_response({
        "ok": True,
        "player": {
            "id": player["id"],
            "username": player["username"],
            "role": player["role"],
            "house_id": player["house_id"],
            "is_super_admin": player["is_super_admin"],
        }
    })


# ==========================================
# ADMIN: LIST PLAYERS
# ==========================================

async def admin_players_handler(request):
    admin, error = await require_admin(request)

    if error:
        return error

    try:
        page = int(request.query.get("page", "1"))
        limit = int(request.query.get("limit", "50"))
    except ValueError:
        return json_error(
            "invalid_pagination",
            400
        )

    page = max(1, min(page, 100000))
    limit = max(1, min(limit, 100))
    offset = (page - 1) * limit

    search = request.query.get("search", "").strip()

    if len(search) > 80:
        return json_error(
            "search_too_long",
            400
        )

    try:
        async with db_pool.acquire() as connection:

            rows = await connection.fetch(
                """
                SELECT
                    id,
                    username,
                    role,
                    house_id,
                    is_active,
                    is_super_admin,
                    created_at
                FROM players
                WHERE
                    $1 = ''
                    OR username ILIKE '%' || $1 || '%'
                    OR id::text = $1
                ORDER BY id
                LIMIT $2 OFFSET $3
                """,
                search,
                limit,
                offset
            )

            total = await connection.fetchval(
                """
                SELECT COUNT(*)
                FROM players
                WHERE
                    $1 = ''
                    OR username ILIKE '%' || $1 || '%'
                    OR id::text = $1
                """,
                search
            )

        return web.json_response({
            "ok": True,
            "players": [
                {
                    "id": row["id"],
                    "username": row["username"],
                    "role": row["role"],
                    "house_id": row["house_id"],
                    "is_active": row["is_active"],
                    "is_super_admin": row["is_super_admin"],
                    "created_at": row["created_at"].isoformat(),
                }
                for row in rows
            ],
            "page": page,
          

            "total": total,
            "pages": (total + limit - 1) // limit,
        })

    except Exception:
        print("Admin players list failed", flush=True)
        return json_error("players_list_failed", 500)


# ==========================================
# ADMIN: CHANGE PLAYER STATUS
# ==========================================

async def admin_player_status_handler(request):
    admin, error = await require_admin(request)
    if error:
        return error

    try:
        player_id = int(request.match_info["player_id"])
        body = await request.json()
    except (ValueError, TypeError, json.JSONDecodeError):
        return json_error("invalid_request", 400)

    if not isinstance(body, dict) or not isinstance(body.get("is_active"), bool):
        return json_error("invalid_request", 400)

    if player_id == admin["id"]:
        return json_error("cannot_change_own_status", 403)

    try:
        async with db_pool.acquire() as connection:
            async with connection.transaction():
                target = await connection.fetchrow(
                    """
                    SELECT id, role, is_super_admin
                    FROM players
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    player_id
                )

                if not target:
                    return json_error("player_not_found", 404)

                if target["role"] == "admin" or target["is_super_admin"]:
                    if not admin["is_super_admin"]:
                        return json_error("super_admin_required", 403)

                await connection.execute(
                    """
                    UPDATE players
                    SET is_active = $1
                    WHERE id = $2
                    """,
                    body["is_active"],
                    player_id
                )

                await write_admin_log(
                    connection,
                    admin["id"],
                    "change_player_status",
                    player_id,
                    {"is_active": body["is_active"]}
                )

        return web.json_response({"ok": True})

    except Exception:
        print("Player status update failed", flush=True)
        return json_error("status_update_failed", 500)


# ==========================================
# ADMIN: CHANGE PLAYER ROLE
# ==========================================

async def admin_player_role_handler(request):
    admin, error = await require_admin(request)
    if error:
        return error

    try:
        player_id = int(request.match_info["player_id"])
        body = await request.json()
    except (ValueError, TypeError, json.JSONDecodeError):
        return json_error("invalid_request", 400)

    if not isinstance(body, dict):
        return json_error("invalid_request", 400)

    new_role = body.get("role")

    if new_role not in ALLOWED_ROLES:
        return json_error("invalid_role", 400)

    if player_id == admin["id"]:
        return json_error("cannot_change_own_role", 403)

    try:
        async with db_pool.acquire() as connection:
            async with connection.transaction():
                target = await connection.fetchrow(
                    """
                    SELECT id, role, is_super_admin
                    FROM players
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    player_id
                )

                if not target:
                    return json_error("player_not_found", 404)

                if (
                    new_role == "admin"
                    or target["role"] == "admin"
                    or target["is_super_admin"]
                ):
                    if not admin["is_super_admin"]:
                        return json_error("super_admin_required", 403)

                if target["is_super_admin"] and new_role != "admin":
                    return json_error("cannot_demote_super_admin", 403)

                await connection.execute(
                    """
                    UPDATE players
                    SET role = $1
                    WHERE id = $2
                    """,
                    new_role,
                    player_id
                )

                await write_admin_log(
                    connection,
                    admin["id"],
                    "change_player_role",
                    player_id,
                    {"old_role": target["role"], "new_role": new_role}
                )

        return web.json_response({"ok": True})

    except Exception:
        print("Player role update failed", flush=True)
        return json_error("role_update_failed", 500)


# ==========================================
# ADMIN: VIEW AUDIT LOGS
# ==========================================

async def admin_logs_handler(request):
    admin, error = await require_admin(request)
    if error:
        return error

    try:
        limit = int(request.query.get("limit", "50"))
        limit = max(1, min(limit, 100))

        async with db_pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT
                    id,
                    admin_id,
                    action,
                    target_player_id,
                    details,
                    created_at
                FROM admin_audit_logs
                ORDER BY id DESC
                LIMIT $1
                """,
                limit
            )

        return web.json_response({
            "ok": True,
            "logs": [
                {
                    "id": row["id"],
                    "admin_id": row["admin_id"],
                    "action": row["action"],
                    "target_player_id": row["target_player_id"],
                    "details": row["details"],
                    "created_at": row["created_at"].isoformat(),
                }
                for row in rows
            ]
        })

    except Exception:
        print("Admin logs retrieval failed", flush=True)
        return json_error("logs_failed", 500)


# ==========================================
# STARTUP AND SHUTDOWN
# ==========================================

async def on_startup(app):
    global db_pool

    if not WEBAPP_FILE.is_file():
        raise RuntimeError("static/index.html not found")

    db_pool = await asyncpg.create_pool(
        host=os.environ["PGHOST"],
        database=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        ssl="require",
        min_size=1,
        max_size=10,
    )

    async with db_pool.acquire() as connection:
        await connection.execute("SELECT 1")

        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_audit_logs (
                id BIGSERIAL PRIMARY KEY,
                admin_id BIGINT NOT NULL REFERENCES players(id),
                action TEXT NOT NULL,
                target_player_id BIGINT REFERENCES players(id),
                details JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

        await connection.execute(
            """
            UPDATE players
            SET is_super_admin = TRUE
            WHERE id = $1 AND role = 'admin'
            """,
            SUPER_ADMIN_ID
        )

    await bot.set_webhook(
        f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
    )

    print("Database connected and webhook configured", flush=True)


async def on_shutdown(app):
    global db_pool

    if db_pool is not None:
        await db_pool.close()
        db_pool = None

    await bot.session.close()
    print("Application stopped", flush=True)


# ==========================================
# APPLICATION
# ==========================================

def create_app():
    app = web.Application()

    app.router.add_get(
        "/",
        lambda request: web.Response(text="Dance of Dragons is running.")
    )

    app.router.add_get(
        "/app",
        lambda request: web.FileResponse(WEBAPP_FILE)
    )

    app.router.add_post(
        "/api/auth/telegram",
        telegram_auth_handler
    )

    app.router.add_post(
        "/api/admin/bootstrap",
        admin_bootstrap_handler
    )

    app.router.add_get(
        "/api/me",
        me_handler
    )

    app.router.add_post(
        "/api/logout",
        logout_handler
    )

    app.router.add_get(
        "/api/admin/players",
        admin_players_handler
    )

    app.router.add_patch(
        "/api/admin/players/{player_id}/status",
        admin_player_status_handler
    )

    app.router.add_patch(
        "/api/admin/players/{player_id}/role",
        admin_player_role_handler
    )

    app.router.add_get(
        "/api/admin/logs",
        admin_logs_handler
    )

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    ).register(
        app,
        path=WEBHOOK_PATH
    )

    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    return app


if __name__ == "__main__":
    web.run_app(
        create_app(),
        host=WEB_SERVER_HOST,
        port=WEB_SERVER_PORT
            )
