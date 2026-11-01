
import os
import time
import json
import hmac
import hashlib
import secrets
import asyncpg

from urllib.parse import parse_qsl
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

PERMISSION_KEYS = {
    "players": "مدیریت بازیکنان",
    "houses": "مدیریت خاندان‌ها",
    "territories": "مدیریت قلمروها",
    "economy": "مدیریت اقتصاد",
    "dragons": "مدیریت اژدهایان",
    "characters": "مدیریت شخصیت‌ها",
    "events": "مدیریت رویدادها",
    "war": "مدیریت جنگ‌ها",
    "diplomacy": "مدیریت دیپلماسی",
    "logs": "مشاهده گزارش‌ها",
}

ACCESS_LEVELS = {"none", "view", "edit"}


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
                    web_app=WebAppInfo(url=f"{WEBHOOK_BASE_URL}/app")
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

        if not hmac.compare_digest(calculated_hash, received_hash):
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
        VALUES ($1, $2, NOW(), NOW() + INTERVAL '7 days')
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
        return None, json_error("database_unavailable", 503)

    token = get_bearer_token(request)

    if not token:
        return None, json_error("missing_session_token", 401)

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
            return None, json_error("invalid_or_expired_session", 401)

        return player, None

    except Exception:
        print("Session validation failed", flush=True)
        return None, json_error("authentication_failed", 500)


async def require_admin(request):
    player, error = await get_authenticated_player(request)

    if error:
        return None, error

    if player["role"] != "admin":
        return None, json_error("admin_required", 403)

    return player, None


async def require_super_admin(request):
    player, error = await require_admin(request)

    if error:
        return None, error

    # فقط شناسه 1 سوپرادمین است.
    if (
        player["id"] != SUPER_ADMIN_ID
        or not player["is_super_admin"]
    ):
        return None, json_error("super_admin_required", 403)

    return player, None


async def require_permission(request, permission_key, minimum="view"):
    player, error = await get_authenticated_player(request)

    if error:
        return None, error

    if player["role"] != "admin":
        return None, json_error("admin_required", 403)

    if permission_key not in PERMISSION_KEYS:
        return None, json_error("invalid_permission", 400)

    if minimum not in {"view", "edit"}:
        return None, json_error("invalid_required_level", 400)

    # سوپرادمین اصلی دسترسی کامل دارد.
    if (
        player["id"] == SUPER_ADMIN_ID
        and player["is_super_admin"]
    ):
        return player, None

    required_rank = {"none": 0, "view": 1, "edit": 2}

    try:
        async with db_pool.acquire() as connection:
            granted = await connection.fetchval(
                """
                SELECT access_level
                FROM admin_permissions
                WHERE player_id = $1
                  AND permission_key = $2
                """,
                player["id"],
                permission_key
            )

        granted_rank = required_rank.get(granted, 0)

        if granted_rank < required_rank[minimum]:
            return None, json_error("permission_denied", 403)

        return player, None

    except Exception:
        print("Permission check failed", flush=True)
        return None, json_error("permission_check_failed", 500)


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
# TELEGRAM LOGIN
# ==========================================

async def telegram_auth_handler(request):
    if db_pool is None:
        return json_error("database_unavailable", 503)

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
        return json_error("invalid_telegram_auth", 401)

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
                    return json_error("account_not_found", 403)

                if not player["is_active"]:
                    return json_error("account_disabled", 403)

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
        return json_error("authentication_failed", 500)


# ==========================================
# LOGOUT
# ==========================================

async def logout_handler(request):
    if db_pool is None:
        return json_error("database_unavailable", 503)

    token = get_bearer_token(request)

    if not token:
        return json_error("missing_session_token", 401)

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    try:
        async with db_pool.acquire() as connection:
            await connection.execute(
                """
                UPDATE player_sessions
                SET revoked_at = NOW()
                WHERE session_token_hash = $1
                  AND revoked_at IS NULL
                """,
                token_hash
            )

        return web.json_response({"ok": True})

    except Exception:
        print("Logout failed", flush=True)
        return json_error("logout_failed", 500)


# ==========================================
# FIRST ADMIN BOOTSTRAP
# ==========================================

async def admin_bootstrap_handler(request):
    if db_pool is None:
        return json_error("database_unavailable", 503)

    if len(ADMIN_SETUP_CODE) < 24:
        return json_error("admin_setup_not_configured", 503)

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
        return json_error("invalid_setup_code", 403)

    auth_result = validate_telegram_init_data(init_data)

    if not auth_result:
        return json_error("invalid_telegram_auth", 401)

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
                        SELECT 1 FROM players WHERE role = 'admin'
                    )
                    """
                )

                if existing_admin:
                    return json_error("admin_already_exists", 403)

                existing_player = await connection.fetchrow(
                    """
                    SELECT id FROM players WHERE telegram_id = $1
                    """,
                    telegram_id
                )

                if existing_player:
                    return json_error("telegram_already_registered", 409)

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
                        $1, NULL, $2, 'admin', NULL,
                        TRUE, TRUE, NOW(), $3
                    )
                    RETURNING
                        id, username, role, house_id,
                        is_active, is_super_admin
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
        return json_error("account_conflict", 409)

    except Exception:
        print("Admin bootstrap failed", flush=True)
        return json_error("admin_setup_failed", 500)


# ==========================================
# CURRENT PLAYER
# ==========================================

async def me_handler(request):
    player, error = await get_authenticated_player(request)

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
    admin, error = await require_permission(
        request, "players", "view"
    )

    if error:
        return error

    try:
        page = int(request.query.get("page", "1"))
        limit = int(request.query.get("limit", "50"))
    except ValueError:
        return json_error("invalid_pagination", 400)

    page = max(1, min(page, 100000))
    limit = max(1, min(limit, 100))
    offset = (page - 1) * limit

    search = request.query.get("search", "").strip()

    if len(search) > 80:
        return json_error("search_too_long", 400)

    try:
        async with db_pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT
                    id, username, role, house_id,
                    is_active, is_super_admin, created_at
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

                        "house_id": row["house_id"],
                    "is_active": row["is_active"],
                    "is_super_admin": row["is_super_admin"],
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "per_page": limit,
        })

    except Exception as e:
        logger.exception("Admin players handler error")
        return web.json_response(
            {"ok": False, "error": "internal_server_error"},
            status=500
        )


async def admin_player_status_handler(request):
    admin, error = await require_permission(
        request, "players", "edit"
    )
    if error:
        return error

    try:
        player_id = int(request.match_info["player_id"])
        data = await request.json()
        is_active = data.get("is_active")

        if not isinstance(is_active, bool):
            return web.json_response(
                {"ok": False, "error": "invalid_is_active"},
                status=400
            )

        async with request.app["db"].acquire() as connection:
            target = await connection.fetchrow(
                """
                SELECT id, role, is_super_admin
                FROM players
                WHERE id = $1
                """,
                player_id
            )

            if not target:
                return web.json_response(
                    {"ok": False, "error": "player_not_found"},
                    status=404
                )

            if target["is_super_admin"]:
                return web.json_response(
                    {"ok": False, "error": "cannot_change_super_admin"},
                    status=403
                )

            if target["role"] == "admin" and not admin["is_super_admin"]:
                return web.json_response(
                    {"ok": False, "error": "cannot_change_admin"},
                    status=403
                )

            await connection.execute(
                """
                UPDATE players
                SET is_active = $1
                WHERE id = $2
                """,
                is_active,
                player_id
            )

            await connection.execute(
                """
                INSERT INTO admin_audit_logs
                    (admin_id, action, target_player_id, details)
                VALUES ($1, $2, $3, $4)
                """,
                admin["id"],
                "player_status_changed",
                player_id,
                f"is_active={is_active}"
            )

        return web.json_response({"ok": True})

    except (ValueError, TypeError):
        return web.json_response(
            {"ok": False, "error": "invalid_request"},
            status=400
        )
    except Exception:
        logger.exception("Admin player status handler error")
        return web.json_response(
            {"ok": False, "error": "internal_server_error"},
            status=500
        )


async def admin_player_role_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error

    try:
        player_id = int(request.match_info["player_id"])
        data = await request.json()
        role = data.get("role")

        allowed_roles = {
            "player",
            "house_leader",
            "treasurer",
            "admin"
        }

        if role not in allowed_roles:
            return web.json_response(
                {"ok": False, "error": "invalid_role"},
                status=400
            )

        if player_id == SUPER_ADMIN_ID:
            return web.json_response(
                {"ok": False, "error": "cannot_change_super_admin_role"},
                status=403
            )

        async with request.app["db"].acquire() as connection:
            target = await connection.fetchrow(
                "SELECT id, role FROM players WHERE id = $1",
                player_id
            )

            if not target:
                return web.json_response(
                    {"ok": False, "error": "player_not_found"},
                    status=404
                )

            await connection.execute(
                """
                UPDATE players
                SET role = $1
                WHERE id = $2
                """,
                role,
                player_id
            )

            if role != "admin":
                await connection.execute(
                    "DELETE FROM admin_permissions WHERE player_id = $1",
                    player_id
                )

            await connection.execute(
                """
                INSERT INTO admin_audit_logs
                    (admin_id, action, target_player_id, details)
                VALUES ($1, $2, $3, $4)
                """,
                admin["id"],
                "player_role_changed",
                player_id,
                f"role={role}"
            )

        return web.json_response({"ok": True})

    except (ValueError, TypeError):
        return web.json_response(
            {"ok": False, "error": "invalid_request"},
            status=400
        )
    except Exception:
        logger.exception("Admin player role handler error")
        return web.json_response(
            {"ok": False, "error": "internal_server_error"},
            status=500
        )


async def admin_get_permissions_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error

    try:
        player_id = int(request.match_info["player_id"])

        async with request.app["db"].acquire() as connection:
            target = await connection.fetchrow(
                "SELECT id, role FROM players WHERE id = $1",
                player_id
            )

            if not target:
                return web.json_response(
                    {"ok": False, "error": "player_not_found"},
                    status=404
                )

            if target["role"] != "admin":
                return web.json_response(
                    {"ok": False, "error": "target_is_not_admin"},
                    status=400
                )

            rows = await connection.fetch(
                """
                SELECT permission_key, access_level
                FROM admin_permissions
                WHERE player_id = $1
                ORDER BY permission_key
                """,
                player_id
            )

        permissions = {
            key: "none" for key in PERMISSION_KEYS
        }

        for row in rows:
            permissions[row["permission_key"]] = row["access_level"]

        return web.json_response({
            "ok": True,
            "player_id": player_id,
            "permissions": permissions
        })

    except (ValueError, TypeError):
        return web.json_response(
            {"ok": False, "error": "invalid_player_id"},
            status=400
        )
    except Exception:
        logger.exception("Get admin permissions error")
        return web.json_response(
            {"ok": False, "error": "internal_server_error"},
            status=500
        )


async def admin_update_permissions_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error

    try:
        player_id = int(request.match_info["player_id"])
        data = await request.json()
        permissions = data.get("permissions")

        if not isinstance(permissions, dict):
            return web.json_response(
                {"ok": False, "error": "invalid_permissions"},
                status=400
            )

        invalid_keys = set(permissions.keys()) - set(PERMISSION_KEYS)
        if invalid_keys:
            return web.json_response(
                {"ok": False, "error": "invalid_permission_keys"},
                status=400
            )

        for level in permissions.values():
            if level not in ACCESS_LEVELS:
                return web.json_response(
                    {"ok": False, "error": "invalid_access_level"},
                    status=400
                )

        async with request.app["db"].acquire() as connection:
            target = await connection.fetchrow(
                "SELECT id, role FROM players WHERE id = $1",
                player_id
            )

            if not target:
                return web.json_response(
                    {"ok": False, "error": "player_not_found"},
                    status=404
                )

            if target["role"] != "admin" or player_id == SUPER_ADMIN_ID:
                return web.json_response(
                    {"ok": False, "error": "invalid_permission_target"},
                    status=400
                )

            async with connection.transaction():
                for key in PERMISSION_KEYS:
                    level = permissions.get(key, "none")

                    await connection.execute(
                        """
                        INSERT INTO admin_permissions
                            (player_id, permission_key, access_level, granted_by)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (player_id, permission_key)
                        DO UPDATE SET
                            access_level = EXCLUDED.access_level,
                            granted_by = EXCLUDED.granted_by,
                            updated_at = NOW()
                        """,
                        player_id,
                        key,
                        level,
                        admin["id"]
                    )

                await connection.execute(
                    """
                    INSERT INTO admin_audit_logs
                        (admin_id, action, target_player_id, details)
                    VALUES ($1, $2, $3, $4)
                    """,
                    admin["id"],
                    "admin_permissions_updated",
                    player_id,
                    "permissions updated"
                )

        return web.json_response({"ok": True})

    except (ValueError, TypeError):
        return web.json_response(
            {"ok": False, "error": "invalid_request"},
            status=400
        )
    except Exception:
        logger.exception("Update admin permissions error")
        return web.json_response(
            {"ok": False, "error": "internal_server_error"},
            status=500
        )


async def admin_logs_handler(request):
    admin, error = await require_permission(
        request, "logs", "view"
    )
    if error:
        return error

    try:
        limit = min(
            max(int(request.query.get("limit", "50")), 1),
            200
        )

        async with request.app["db"].acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT
                    l.id,
                    l.admin_id,
                    p.username AS admin_username,
                    l.action,
                    l.target_player_id,
                    l.details,
                    l.created_at
                FROM admin_audit_logs l
                LEFT JOIN players p ON p.id = l.admin_id
                ORDER BY l.id DESC
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
                    "admin_username": row["admin_username"],
                    "action": row["action"],
                    "target_player_id": row["target_player_id"],
                    "details": row["details"],
                    "created_at": row["created_at"].isoformat()
                    if row["created_at"] else None
                }
                for row in rows
            ]
        })

    except Exception:
        logger.exception("Admin logs handler error")
        return web.json_response(
            {"ok": False, "error": "internal_server_error"},
            status=500
        )

async def on_startup(app):
    logger.info("Starting Dance of Dragons...")

    try:
        app["db"] = await asyncpg.create_pool(DATABASE_URL)

        async with app["db"].acquire() as connection:
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS admin_permissions (
                    id BIGSERIAL PRIMARY KEY,
                    player_id INTEGER NOT NULL
                        REFERENCES players(id) ON DELETE CASCADE,
                    permission_key TEXT NOT NULL,
                    access_level TEXT NOT NULL DEFAULT 'none'
                        CHECK (access_level IN ('none', 'view', 'edit')),
                    granted_by INTEGER
                        REFERENCES players(id) ON DELETE SET NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (player_id, permission_key)
                )
            """)

            await connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_admin_permissions_player
                ON admin_permissions(player_id)
            """)

            await connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_admin_permissions_key
                ON admin_permissions(permission_key)
            """)

            await connection.execute("""
                UPDATE players
                SET is_super_admin = FALSE
                WHERE id != $1
            """, SUPER_ADMIN_ID)

            await connection.execute("""
                UPDATE players
                SET is_super_admin = TRUE
                WHERE id = $1 AND role = 'admin'
            """, SUPER_ADMIN_ID)

        logger.info("Database connected successfully")

        if BOT_TOKEN:
            await bot.set_webhook(WEBHOOK_URL)
            logger.info("Telegram webhook configured")

    except Exception:
        logger.exception("Startup error")
        raise


async def on_cleanup(app):
    if "db" in app:
        await app["db"].close()
        logger.info("Database pool closed")


async def index_handler(request):
    if not WEBAPP_FILE.exists():
        return web.Response(
            text="index.html not found",
            status=404
        )

    return web.FileResponse(WEBAPP_FILE)


def create_app():
    app = web.Application()

    app.router.add_get("/", index_handler)
    app.router.add_post("/webhook", webhook_handler)

    app.router.add_get("/api/me", me_handler)

    app.router.add_post("/api/auth", auth_handler)
    app.router.add_post("/api/logout", logout_handler)

    app.router.add_get("/api/admin/players", admin_players_handler)

    app.router.add_patch(
        "/api/admin/players/{player_id}/status",
        admin_player_status_handler
    )

    app.router.add_patch(
        "/api/admin/players/{player_id}/role",
        admin_player_role_handler
    )

    app.router.add_get(
        "/api/admin/players/{player_id}/permissions",
        admin_get_permissions_handler
    )

    app.router.add_put(
        "/api/admin/players/{player_id}/permissions",
        admin_update_permissions_handler
    )

    app.router.add_get("/api/admin/logs", admin_logs_handler)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000"))
        )
