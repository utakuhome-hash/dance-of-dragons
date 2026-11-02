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

HOUSE_SEEDS = [
    [
        "استارک",
        "وینترفل"
    ],
    [
        "کارستارک",
        "کارهولد"
    ],
    [
        "داستین",
        "باروتون"
    ],
    [
        "آمبر",
        "لست هرت"
    ],
    [
        "آرین",
        "ایری"
    ],
    [
        "رویس",
        "رانستون"
    ],
    [
        "کوربری",
        "هارتس هوم"
    ],
    [
        "گریجوی",
        "پایک"
    ],
    [
        "هارلاو",
        "ده برج"
    ],
    [
        "گودبروتر",
        "گریت ویک"
    ],
    [
        "بلک‌تاید",
        "بلک‌تاید"
    ],
    [
        "تالی",
        "ریوران"
    ],
    [
        "فری",
        "تویینز"
    ],
    [
        "برکن",
        "استون هِج"
    ],
    [
        "بلک‌وود",
        "ریون‌تری هال"
    ],
    [
        "لنیستر",
        "کسترلی راک"
    ],
    [
        "کراکهال",
        "کراکهال"
    ],
    [
        "لفورد",
        "گلدن توث"
    ],
    [
        "تارگرین",
        "کینگزلندینگ"
    ],
    [
        "سیلتیگار",
        "کلاو آیل"
    ],
    [
        "ولاریون",
        "دریفت‌مارک"
    ],
    [
        "دارکلین",
        "دانسکندیل"
    ],
    [
        "بارثیون",
        "استورمزاند"
    ],
    [
        "کارون",
        "نایت‌سانگ"
    ],
    [
        "فل",
        "فل‌وود هال"
    ],
    [
        "سوان",
        "استون‌هلم"
    ],
    [
        "تایرل",
        "های‌گاردن"
    ],
    [
        "ردواین",
        "آربور"
    ],
    [
        "های‌تاور",
        "اولدتاون"
    ],
    [
        "تارلی",
        "هورن هیل"
    ],
    [
        "مارتل",
        "سان‌اسپیر"
    ],
    [
        "دین",
        "استارفال"
    ],
    [
        "یرونوود",
        "یرونوود"
    ],
    [
        "آلیرین",
        "گادزگریس"
    ],
    [
        "فاولر",
        "اسکای‌ریچ"
    ]
]

    [
        "لارجنت",
        "نامشخص"
    ],
    [
        "کارگیل",
        "نامشخص"
    ],


# Existing Telegram accounts mapped to their canonical Westerosi houses.
# Applied at startup so existing players receive their house without manual admin edits.
PLAYER_HOUSE_ASSIGNMENTS = [
    (7355922500, "لنیستر"),
    (7066209583, "کراکهال"),
    (6850075647, "لفورد"),
    (7379737762, "لنیستر"),
    (8925141426, "گریجوی"),
    (6478660512, "هارلاو"),
    (5429973583, "گریجوی"),
    (6989733419, "گودبروتر"),
    (5134846328, "کارون"),
    (6902712240, "بارثیون"),
    (1117348681, "بارثیون"),
    (6008315341, "داستین"),
    (8772075836, "کارستارک"),
    (8848754881, "استارک"),
    (7847392550, "استارک"),
    (6653129379, "آرین"),
    (7330786403, "کوربری"),
    (7126510685, "رویس"),
    (8852092094, "یرونوود"),
    (130805771, "مارتل"),
    (8989395676, "تالی"),
    (7492081507, "بلک‌وود"),
    (7936248304, "فری"),
    (6541635048, "ولاریون"),
    (8511148410, "های‌تاور"),
    (8345844522, "ردواین"),
    (6531093504, "تایرل"),
    (8849113201, "های‌تاور"),
    (435808866, "تایرل"),
    (1214060391, "تایرل"),
    (5269911726, "های‌تاور"),
    (8605396069, "تارلی"),
    (7650983591, "تارگرین"),
    (5632444639, "تارگرین"),
    (6751495290, "ولاریون"),
    (8897601678, "تارگرین"),
    (8845823478, "تارگرین"),
    (7551277757, "تارگرین"),
    (6915810212, "استارک"),
    (8590353980, "لارجنت"),
    (6075025172, "تارگرین"),
    (7865635509, "لنیستر"),
    (6523502457, "تارگرین"),
    (5986557687, "تالی"),
    (8128459841, "سوان"),
    (5990697440, "آرین"),
    (6283332805, "کوربری"),
    (8821942455, "آرین"),
    (8537207185, "کارگیل"),
]

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    required = ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError("Missing database environment variables: " + ", ".join(missing))
    DATABASE_URL = (
        f"postgresql://{quote_plus(os.environ['PGUSER'])}:"
        f"{quote_plus(os.environ['PGPASSWORD'])}@{os.environ['PGHOST']}:"
        f"{os.getenv('PGPORT', '5432')}/{os.environ['PGDATABASE']}"
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
                   h.name AS house_name, p.is_active, p.is_super_admin
            FROM player_sessions s
            JOIN players p ON p.id = s.player_id
            LEFT JOIN houses h ON h.id = p.house_id
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
            SELECT p.id, p.username, p.telegram_id, p.role, p.house_id,
                   h.name AS house_name, p.is_active, p.is_super_admin
            FROM players p
            LEFT JOIN houses h ON h.id = p.house_id
            WHERE p.telegram_id = $1
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
            "house_name": player["house_name"],
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
                SELECT p.id, p.username, p.telegram_id, p.role, p.house_id,
                       h.name AS house_name, p.is_active, p.is_super_admin
                FROM players p
                LEFT JOIN houses h ON h.id = p.house_id
                WHERE p.username ILIKE $1
                   OR p.telegram_id::text ILIKE $1
                   OR p.id::text ILIKE $1
                ORDER BY p.id DESC
                LIMIT $2 OFFSET $3
                """,
                pattern, per_page, offset,
            )
        else:
            total = await conn.fetchval("SELECT COUNT(*) FROM players")
            rows = await conn.fetch(
                """
                SELECT p.id, p.username, p.telegram_id, p.role, p.house_id,
                       h.name AS house_name, p.is_active, p.is_super_admin
                FROM players p
                LEFT JOIN houses h ON h.id = p.house_id
                ORDER BY p.id DESC
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


async def admin_houses_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, castle FROM houses ORDER BY name"
        )
    return web.json_response({"ok": True, "houses": [dict(row) for row in rows]})


async def admin_assign_house_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    try:
        player_id = int(request.match_info["player_id"])
        data = await request.json()
        raw_house_id = data.get("house_id")
        house_id = int(raw_house_id) if raw_house_id not in (None, "") else None
    except (ValueError, TypeError):
        return json_error("invalid_house_assignment")

    async with request.app["db"].acquire() as conn:
        if house_id is not None:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM houses WHERE id = $1)",
                house_id,
            )
            if not exists:
                return json_error("house_not_found", 404)
        row = await conn.fetchrow(
            """
            UPDATE players SET house_id = $1
            WHERE id = $2
            RETURNING id, username, house_id
            """,
            house_id, player_id,
        )
    if not row:
        return json_error("player_not_found", 404)
    return web.json_response({"ok": True, "player": dict(row)})


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


async def mail_players_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.id, p.username, p.house_id, h.name AS house_name
            FROM players p
            LEFT JOIN houses h ON h.id = p.house_id
            WHERE p.is_active = TRUE AND p.id <> $1
            ORDER BY p.username, p.id
            """,
            player["id"],
        )
    return web.json_response({"ok": True, "players": [dict(row) for row in rows]})


async def mail_list_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    box = request.query.get("box", "inbox")
    if box not in ("inbox", "outbox"):
        return json_error("invalid_mailbox")
    column = "recipient_player_id" if box == "inbox" else "sender_player_id"
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT l.id, l.subject, l.body, l.category, l.created_at,
                   l.read_at, p.id AS other_player_id, p.username AS other_player
            FROM game_letters l
            JOIN players p ON p.id = CASE WHEN $1 = 'inbox'
                THEN l.sender_player_id ELSE l.recipient_player_id END
            WHERE l.{column} = $2
            ORDER BY l.created_at DESC
            LIMIT 100
            """,
            box, player["id"],
        )
    letters = []
    for row in rows:
        letter = dict(row)
        for field in ("created_at", "read_at"):
            if letter.get(field) is not None:
                letter[field] = letter[field].isoformat()
        letters.append(letter)
    return web.json_response({"ok": True, "letters": letters})


async def mail_send_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    try:
        data = await request.json()
    except Exception:
        return json_error("invalid_json")
    try:
        recipient_id = int(data.get("recipient_id", 0))
    except (TypeError, ValueError):
        return json_error("invalid_recipient")
    subject = str(data.get("subject", "")).strip()
    body = str(data.get("body", "")).strip()
    category = str(data.get("category", "personal")).strip()
    allowed = {"diplomacy", "marriage", "trade", "military", "warning", "personal"}
    if not subject or len(subject) > 160:
        return json_error("invalid_subject")
    if not body or len(body) > 10000:
        return json_error("invalid_body")
    if category not in allowed:
        return json_error("invalid_category")
    if recipient_id == int(player["id"]):
        return json_error("cannot_message_self")
    async with request.app["db"].acquire() as conn:
        recipient = await conn.fetchrow(
            "SELECT id FROM players WHERE id = $1 AND is_active = TRUE",
            recipient_id,
        )
        if not recipient:
            return json_error("recipient_not_found", 404)
        row = await conn.fetchrow(
            """
            INSERT INTO game_letters
                (sender_player_id, recipient_player_id, subject, body, category, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            RETURNING id, created_at
            """,
            player["id"], recipient_id, subject, body, category,
        )
    letter = dict(row)
    if letter.get("created_at") is not None:
        letter["created_at"] = letter["created_at"].isoformat()
    return web.json_response({"ok": True, "letter": letter}, status=201)


async def mail_read_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    try:
        letter_id = int(request.match_info["letter_id"])
    except (TypeError, ValueError):
        return json_error("invalid_letter_id")
    async with request.app["db"].acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE game_letters SET read_at = COALESCE(read_at, NOW())
            WHERE id = $1 AND recipient_player_id = $2
            RETURNING id
            """,
            letter_id, player["id"],
        )
    if not row:
        return json_error("letter_not_found", 404)
    return web.json_response({"ok": True})


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
    async with app["db"].acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS houses (
                id BIGSERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                sigil TEXT,
                castle VARCHAR(150),
                treasury BIGINT NOT NULL DEFAULT 0,
                food BIGINT NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        for house_name, castle_name in HOUSE_SEEDS:
            await conn.execute(
                """
                INSERT INTO houses (name, castle)
                VALUES ($1, $2)
                ON CONFLICT (name) DO NOTHING
                """,
                house_name, castle_name,
            )
        for telegram_id, house_name in PLAYER_HOUSE_ASSIGNMENTS:
            await conn.execute(
                """
                UPDATE players
                SET house_id = (SELECT id FROM houses WHERE name = $2)
                WHERE telegram_id = $1
                """,
                telegram_id, house_name,
            )
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS game_letters (
                id BIGSERIAL PRIMARY KEY,
                sender_player_id BIGINT NOT NULL REFERENCES players(id),
                recipient_player_id BIGINT NOT NULL REFERENCES players(id),
                subject VARCHAR(160) NOT NULL,
                body TEXT NOT NULL,
                category VARCHAR(20) NOT NULL DEFAULT 'personal',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                read_at TIMESTAMPTZ
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS game_letters_inbox_idx ON game_letters (recipient_player_id, created_at DESC)")
        await conn.execute("CREATE INDEX IF NOT EXISTS game_letters_outbox_idx ON game_letters (sender_player_id, created_at DESC)")
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
    app.router.add_get("/api/admin/houses", admin_houses_handler)
    app.router.add_put("/api/admin/players/{player_id}/house", admin_assign_house_handler)
    app.router.add_post("/api/admin/players", admin_add_player_handler)
    app.router.add_get("/api/mail/players", mail_players_handler)
    app.router.add_get("/api/mail", mail_list_handler)
    app.router.add_post("/api/mail", mail_send_handler)
    app.router.add_post("/api/mail/{letter_id}/read", mail_read_handler)

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=WEB_SERVER_PORT)
