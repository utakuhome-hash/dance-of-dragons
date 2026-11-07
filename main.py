import asyncio
import json
import logging
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
from aiogram.exceptions import TelegramRetryAfter
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application


BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_BASE_URL = os.environ["WEBHOOK_BASE_URL"].strip().rstrip("/")
if WEBHOOK_BASE_URL.startswith("http://"):
    WEBHOOK_BASE_URL = "https://" + WEBHOOK_BASE_URL[len("http://"): ]
elif not WEBHOOK_BASE_URL.startswith("https://"):
    WEBHOOK_BASE_URL = "https://" + WEBHOOK_BASE_URL
WEBHOOK_PATH = "/telegram-webhook"
WEBHOOK_URL = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
WEB_SERVER_PORT = int(os.getenv("PORT", "10000"))

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_FILE = BASE_DIR / "static" / "index.html"

TRADE_GOODS = {
    "چوب", "سنگ", "آهن", "غذا", "اسب جنگی", "خز", "پشم", "شراب",
    "ادویه", "آهن سیاه", "نمک",
}

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
    ],
    [
        "لارجنت",
        "نامشخص"
    ],
    [
        "کارگیل",
        "نامشخص"
    ]
]


# Existing Telegram accounts mapped to their canonical Westerosi houses.
# Applied at startup so existing players receive their house without manual admin edits.
PLAYER_HOUSE_ASSIGNMENTS = [
    (7355922500, "لنیستر"),
    (7865635509, "لنیستر"),
    (7379737762, "لنیستر"),
    (1606528421, "لنیستر"),
    (7066209583, "کراکهال"),
    (6850075647, "لفورد"),
    (7379737762, "لنیستر"),
    (7798537474, "برکن"),
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
    (7650983591, "ولاریون"),
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
    (82773653, "تارگرین"),
    (6552600701, "های‌تاور"),
    (1679850486, "تارگرین"),
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
            web_app=WebAppInfo(url=f"{WEBHOOK_BASE_URL}/play-v5?build=20261106m")
        )]
    ])
    return keyboard


@dp.message(CommandStart())
async def start_handler(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1].strip() if len(parts) > 1 else ""
    if payload.startswith("desktoplogin_"):
        code = payload[len("desktoplogin_"):]
        if not code or len(code) > 80 or not db_pool:
            await message.answer("درخواست ورود معتبر نیست یا منقضی شده است. دوباره از صفحه بازی درخواست ورود بده.")
            return
        async with db_pool.acquire() as conn:
            request_row = await conn.fetchrow(
                "SELECT code FROM desktop_login_requests WHERE code=$1 AND expires_at > NOW() AND session_token IS NULL FOR UPDATE",
                code,
            )
            if not request_row:
                await message.answer("این درخواست ورود منقضی شده یا قبلاً استفاده شده است. صفحه بازی را تازه‌سازی و دوباره درخواست بده.")
                return
            player = await conn.fetchrow(
                """SELECT p.id, p.username, p.telegram_id, p.role, p.house_id,
                          COALESCE(NULLIF(p.castle_name, ''), h.castle) AS castle_name,
                          h.name AS house_name, p.is_active, p.is_super_admin
                   FROM players p LEFT JOIN houses h ON h.id=p.house_id
                   WHERE p.telegram_id=$1""",
                message.from_user.id,
            )
            if not player or not player["is_active"]:
                await message.answer("برای این حساب تلگرام بازیکن فعال ثبت نشده است. با مدیر بازی تماس بگیر.")
                return
            token = secrets.token_urlsafe(48)
            await conn.execute(
                """INSERT INTO player_sessions
                   (player_id, session_token_hash, created_at, expires_at, revoked_at)
                   VALUES ($1,$2,NOW(),NOW()+INTERVAL '7 days',NULL)""",
                player["id"], hash_session_token(token),
            )
            await conn.execute(
                """UPDATE desktop_login_requests SET telegram_id=$1, player_id=$2,
                   session_token=$3, approved_at=NOW() WHERE code=$4""",
                message.from_user.id, player["id"], token, code,
            )
        await message.answer("ورود شما تأیید شد. به صفحه بازی در کامپیوتر برگردید؛ ورود به‌صورت خودکار تکمیل می‌شود.")
        return
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
        safe_user = {
            "id": telegram_id,
            "username": str(user.get("username", ""))[:64],
            "first_name": str(user.get("first_name", ""))[:128],
            "last_name": str(user.get("last_name", ""))[:128],
        }
        return telegram_id, auth_date, safe_user
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
                   COALESCE(NULLIF(p.castle_name, ''), h.castle) AS castle_name,
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
    ):
        return None, json_error("forbidden", 403)
    return player, None


async def desktop_login_request_handler(request):
    if not db_pool:
        return json_error("service_unavailable", 503)
    code = secrets.token_urlsafe(24)
    async with request.app["db"].acquire() as conn:
        await conn.execute("DELETE FROM desktop_login_requests WHERE expires_at < NOW() OR session_token IS NOT NULL")
        await conn.execute(
            "INSERT INTO desktop_login_requests (code, expires_at) VALUES ($1, NOW()+INTERVAL '5 minutes')",
            code,
        )
    me = await bot.get_me()
    if not me.username:
        return json_error("bot_username_unavailable", 503)
    return web.json_response({
        "ok": True,
        "code": code,
        "expires_in": 300,
        "bot_url": f"https://t.me/{me.username}?start=desktoplogin_{code}",
    })


async def desktop_login_status_handler(request):
    code = request.match_info.get("code", "")
    if len(code) < 20 or len(code) > 80:
        return json_error("invalid_login_code", 400)
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT r.player_id, r.session_token, p.username, p.telegram_id,
                          p.role, p.house_id,
                          COALESCE(NULLIF(p.castle_name, ''), h.castle) AS castle_name,
                          h.name AS house_name, p.is_active, p.is_super_admin
                   FROM desktop_login_requests r
                   LEFT JOIN players p ON p.id=r.player_id
                   LEFT JOIN houses h ON h.id=p.house_id
                   WHERE r.code=$1 AND r.expires_at > NOW()
                   FOR UPDATE OF r""",
                code,
            )
            if not row:
                return json_error("login_request_expired", 410)
            if not row["session_token"]:
                return web.json_response({"ok": True, "status": "pending"})
            if not row["is_active"]:
                await conn.execute("DELETE FROM desktop_login_requests WHERE code=$1", code)
                return json_error("account_disabled", 403)
            result = {
                "ok": True,
                "status": "approved",
                "token": row["session_token"],
                "player": {
                    "id": row["player_id"], "username": row["username"],
                    "telegram_id": row["telegram_id"], "role": row["role"],
                    "house_id": row["house_id"], "castle_name": row["castle_name"],
                    "house_name": row["house_name"], "is_active": row["is_active"],
                    "is_super_admin": row["is_super_admin"],
                },
            }
            await conn.execute("DELETE FROM desktop_login_requests WHERE code=$1", code)
    return web.json_response(result)


async def auth_handler(request):
    try:
        data = await request.json()
    except Exception:
        return json_error("invalid_json")

    init_data = data.get("init_data", "")
    validated = validate_telegram_init_data(init_data)
    if not validated:
        return json_error("telegram_auth_failed", 401)

    telegram_id, auth_date, telegram_user = validated
    async with request.app["db"].acquire() as conn:
        player = await conn.fetchrow(
            """
            SELECT p.id, p.username, p.telegram_id, p.role, p.house_id,
                   COALESCE(NULLIF(p.castle_name, ''), h.castle) AS castle_name,
                   h.name AS house_name, p.is_active, p.is_super_admin
            FROM players p
            LEFT JOIN houses h ON h.id = p.house_id
            WHERE p.telegram_id = $1
            """,
            telegram_id,
        )

        if not player:
            await conn.execute(
                """
                INSERT INTO telegram_login_requests
                    (telegram_id, telegram_username, first_name, last_name,
                     first_seen_at, last_seen_at, attempt_count)
                VALUES ($1, $2, $3, $4, NOW(), NOW(), 1)
                ON CONFLICT (telegram_id) DO UPDATE
                SET telegram_username = EXCLUDED.telegram_username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_seen_at = NOW(),
                    attempt_count = telegram_login_requests.attempt_count + 1
                """,
                telegram_id, telegram_user["username"],
                telegram_user["first_name"], telegram_user["last_name"],
            )
            return json_error("account_not_found", 404)
        if not player["is_active"]:
            return json_error("account_disabled", 403)

        await conn.execute(
            "UPDATE players SET telegram_auth_date = $1 WHERE id = $2",
            auth_date, player["id"]
        )

        token = secrets.token_urlsafe(48)
        token_hash = hash_session_token(token)
        forwarded_ip = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        ip_address = (forwarded_ip or request.remote or "")[:64] or None
        user_agent = request.headers.get("User-Agent", "")[:1000] or None
        install_id = str(data.get("install_id") or request.headers.get("X-Game-Install-ID", "")).strip()[:80] or None
        await conn.execute(
            """
            INSERT INTO player_sessions
                (player_id, session_token_hash, created_at, expires_at, revoked_at, ip_address, user_agent, install_id)
            VALUES ($1, $2, NOW(), NOW() + INTERVAL '7 days', NULL, $3, $4, $5)
            """,
            player["id"], token_hash, ip_address, user_agent, install_id
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
            "castle_name": player["castle_name"],
            "house_name": player["house_name"],
            "is_active": player["is_active"],
            "is_super_admin": player["is_super_admin"],
        }
    })


KINGSLANDING_COURT_TELEGRAM_IDS = [
    6523502457,  # Aegon
    1679850486,  # Aemond
    6075025172,  # Helaena
    1057851448,  # Alicent
    8586298875,  # Erryk Cargyll
    8590353980,  # Ser Luthor
    8893096451,  # Ser Criston Cole
    8774384348,  # Ulf White
    8823771080,  # Grand Maester
]

DRAGONSTONE_COURT_TELEGRAM_IDS = [
    5632444639,  # Rhaenyra Targaryen
    7551277757,  # Daemon Targaryen
    8897601678,  # Rhaenys Targaryen
    8845823478,  # Baela Targaryen
    6751495290,  # Jacaerys Velaryon
    8082440635,  # Addam Velaryon
    7122047466,  # Hugh Hammer
    8537207185,  # Erryk Cargyll
    1183064616,  # Ser Lorent Marbrand
    8925154779,  # Ser Willam Royce
]

DRIFTMARK_COURT_TELEGRAM_IDS = [
    7650983591,  # Corlys Velaryon
    6541635048,  # Alan Velaryon
]

CLAW_ISLE_COURT_TELEGRAM_IDS = [
    8128459841,  # Bartimos Celtigar
]

DUSKENDALE_COURT_TELEGRAM_IDS = [
    6669583051,  # Reynald Darklyn
]

HIGHGARDEN_COURT_TELEGRAM_IDS = [
    435808866,   # Lionel Tyrell
    1214060391,  # Loras Tyrell
    6531093504,  # Leo Tyrell
]

OLDTOWN_COURT_TELEGRAM_IDS = [
    8511148410,  # Otto Hightower
    8849113201,  # Ormund Hightower
    5269911726,  # Gwayne Hightower
]

ARBOR_COURT_TELEGRAM_IDS = [
    8345844522,  # Garth Redwyne
]

TARLY_COURT_TELEGRAM_IDS = [
    8605396069,  # Alan Tarly
]

WINTERFELL_COURT_TELEGRAM_IDS = [
    6915810212,  # Cregan Stark
    7847392550,  # Rickon Stark
    8848754881,  # Benjen Stark
]

KARHOLD_COURT_TELEGRAM_IDS = [
    8772075836,  # Assis Karstark
]

BARROWTON_COURT_TELEGRAM_IDS = [
    6008315341,  # Roderick Dustin
]

CASTERLY_ROCK_COURT_TELEGRAM_IDS = [
    7355922500,  # Jason Lannister
    7865635509,  # Tyland Lannister
    7379737762,  # Loren Lannister
    1606528421,  # Johanna Lannister
]

CRAKEHALL_COURT_TELEGRAM_IDS = [
    7066209583,  # Karent Crakehall
]

# Telegram accounts explicitly introduced as members of the court rosters.
# Provision missing player rows so these users can pass /api/auth/telegram.
COURT_PLAYER_ACCOUNTS = [
    (7650983591, "Corlys Velaryon"),
    (6541635048, "Alan Velaryon"),
    (8128459841, "Bartimos Celtigar"),
    (6669583051, "Reynald Darklyn"),
    (435808866, "Lionel Tyrell"),
    (1214060391, "Loras Tyrell"),
    (6531093504, "Leo Tyrell"),
    (8511148410, "Otto Hightower"),
    (8849113201, "Ormund Hightower"),
    (5269911726, "Gwayne Hightower"),
    (8345844522, "Garth Redwyne"),
    (8605396069, "Alan Tarly"),
    (6915810212, "Cregan Stark"),
    (7847392550, "Rickon Stark"),
    (8848754881, "Benjen Stark"),
    (8772075836, "Assis Karstark"),
    (6008315341, "Roderick Dustin"),
    (7355922500, "Jason Lannister"),
    (7865635509, "Tyland Lannister"),
    (7379737762, "Loren Lannister"),
    (1606528421, "Johanna Lannister"),
    (7066209583, "Karent Crakehall"),
]


async def castle_members_handler(request):
    castle_name = request.match_info["castle_name"].strip()
    if not castle_name or len(castle_name) > 150:
        return json_error("invalid_castle_name")
    normalized_castle = normalize_court_name(castle_name)
    is_kings_landing = normalized_castle in (
        normalize_court_name("کینگزلندینگ"),
        normalize_court_name("King's Landing"),
    )
    is_dragonstone = normalized_castle in (
        normalize_court_name("دراگون‌استون"),
        normalize_court_name("Dragonstone"),
    )
    is_driftmark = normalized_castle in (
        normalize_court_name("دریفت‌مارک"),
        normalize_court_name("Driftmark"),
    )
    is_claw_isle = normalized_castle in (
        normalize_court_name("کلاوآیل"),
        normalize_court_name("کلاور آیل"),
        normalize_court_name("Claw Isle"),
    )
    is_duskendale = normalized_castle in (
        normalize_court_name("دانکدایل"),
        normalize_court_name("دانسکندیل"),
        normalize_court_name("Duskendale"),
    )
    is_highgarden = normalized_castle in (
        normalize_court_name("هایگاردن"),
        normalize_court_name("های‌گاردن"),
        normalize_court_name("Highgarden"),
    )
    is_oldtown = normalized_castle in (
        normalize_court_name("اولد تاون"),
        normalize_court_name("اولدتاؤن"),
        normalize_court_name("Oldtown"),
    )
    is_arbor = normalized_castle in (
        normalize_court_name("آربور"),
        normalize_court_name("The Arbor"),
        normalize_court_name("Arbor"),
    )
    is_horn_hill = normalized_castle in (
        normalize_court_name("هورن‌هیل"),
        normalize_court_name("هورن هیل"),
        normalize_court_name("Horn Hill"),
    )
    is_winterfell = normalized_castle in (
        normalize_court_name("وینترفل"),
        normalize_court_name("Winterfell"),
    )
    is_karhold = normalized_castle in (
        normalize_court_name("کارهولد"),
        normalize_court_name("Karhold"),
    )
    is_barrowton = normalized_castle in (
        normalize_court_name("باروتون"),
        normalize_court_name("Barrowton"),
    )
    is_casterly_rock = normalized_castle in (
        normalize_court_name("کسترلی‌راک"),
        normalize_court_name("کسترلی راک"),
        normalize_court_name("Casterly Rock"),
    )
    is_crakehall = normalized_castle in (
        normalize_court_name("کراکهال"),
        normalize_court_name("کرکهال"),
        normalize_court_name("Crakehall"),
    )
    async with request.app["db"].acquire() as conn:
        if is_kings_landing or is_dragonstone or is_driftmark or is_claw_isle or is_duskendale or is_highgarden or is_oldtown or is_arbor or is_horn_hill or is_winterfell or is_karhold or is_barrowton or is_casterly_rock or is_crakehall:
            approved_ids = (
                KINGSLANDING_COURT_TELEGRAM_IDS
                if is_kings_landing
                else DRAGONSTONE_COURT_TELEGRAM_IDS
                if is_dragonstone
                else DRIFTMARK_COURT_TELEGRAM_IDS
                if is_driftmark
                else CLAW_ISLE_COURT_TELEGRAM_IDS
                if is_claw_isle
                else DUSKENDALE_COURT_TELEGRAM_IDS
                if is_duskendale
                else HIGHGARDEN_COURT_TELEGRAM_IDS
                if is_highgarden
                else OLDTOWN_COURT_TELEGRAM_IDS
                if is_oldtown
                else ARBOR_COURT_TELEGRAM_IDS
                if is_arbor
                else TARLY_COURT_TELEGRAM_IDS
                if is_horn_hill
                else WINTERFELL_COURT_TELEGRAM_IDS
                if is_winterfell
                else KARHOLD_COURT_TELEGRAM_IDS
                if is_karhold
                else BARROWTON_COURT_TELEGRAM_IDS
                if is_barrowton
                else CASTERLY_ROCK_COURT_TELEGRAM_IDS
                if is_casterly_rock
                else CRAKEHALL_COURT_TELEGRAM_IDS
            )
            rows = await conn.fetch(
                """
                SELECT p.username, h.name AS house_name
                FROM players p
                LEFT JOIN houses h ON h.id = p.house_id
                WHERE p.is_active = TRUE
                  AND p.telegram_id = ANY($1::bigint[])
                ORDER BY p.username
                """,
                approved_ids,
            )
        else:
            canonical_castle = canonical_travel_castle(castle_name)
            castle_aliases = (
                [canonical_castle, *TRAVEL_CASTLE_ALIASES.get(canonical_castle, [])]
                if canonical_castle else [castle_name]
            )
            normalized_aliases = list({normalize_court_name(value) for value in castle_aliases})
            rows = await conn.fetch(
                """
                SELECT p.username, h.name AS house_name
                FROM players p
                LEFT JOIN houses h ON h.id = p.house_id
                WHERE p.is_active = TRUE
                  AND (
                    p.castle_name = ANY($1::text[])
                    OR h.castle = ANY($1::text[])
                    OR regexp_replace(
                        replace(replace(lower(COALESCE(p.castle_name, '')), 'ي', 'ی'), 'ك', 'ک'),
                        '[[:space:]‌]+', '', 'g'
                    ) = ANY($2::text[])
                    OR regexp_replace(
                        replace(replace(lower(COALESCE(h.castle, '')), 'ي', 'ی'), 'ك', 'ک'),
                        '[[:space:]‌]+', '', 'g'
                    ) = ANY($2::text[])
                  )
                ORDER BY p.username
                """,
                castle_aliases,
                normalized_aliases,
            )
    return web.json_response({
        "ok": True,
        "castle": castle_name,
        "members": [dict(row) for row in rows],
    })



def normalize_court_name(value):
    value = str(value or "").lower().replace("ي", "ی").replace("ك", "ک")
    return "".join(ch for ch in value if not ch.isspace() and ord(ch) != 8204 and ch not in "-'’_")


def court_posts_for_castle(castle_name):
    normalized = normalize_court_name(castle_name)
    if normalized in (normalize_court_name("کینگزلندینگ"), normalize_court_name("King's Landing")):
        return {
            "hand": "دست پادشاه",
            "ships": "استاد کشتی‌ها",
            "laws": "استاد قوانین",
            "coin": "استاد سکه",
            "whispers": "استاد نجواها",
            "army": "فرمانده ارتش سلطنتی",
            "kingsguard": "فرمانده گارد شاهی",
            "citywatch": "فرمانده گارد شهری",
        }
    if normalized in (normalize_court_name("دراگون‌استون"), normalize_court_name("Dragonstone")):
        return {
            "hand": "دست ملکه",
            "ships": "استاد کشتی‌ها",
            "laws": "استاد قوانین",
            "coin": "استاد سکه",
            "whispers": "استاد نجواها",
            "army": "فرمانده ارتش سلطنتی",
            "kingsguard": "فرمانده گارد شاهی",
            "citywatch": "فرمانده گارد شهری",
        }
    return {
        "spymaster": "رئیس جاسوسان قلعه",
        "commander": "فرمانده نیروهای قلعه",
        "treasurer": "خزانه‌دار قلعه",
    }


def player_court_castle(player):
    if not player:
        return None
    try:
        telegram_id = int(player.get("telegram_id") or 0)
    except (TypeError, ValueError):
        telegram_id = 0
    if telegram_id in DRAGONSTONE_COURT_TELEGRAM_IDS:
        return "دراگون‌استون"
    if telegram_id in KINGSLANDING_COURT_TELEGRAM_IDS:
        return "کینگزلندینگ"
    if telegram_id in DRIFTMARK_COURT_TELEGRAM_IDS:
        return "دریفت‌مارک"
    if telegram_id in CLAW_ISLE_COURT_TELEGRAM_IDS:
        return "کلاوآیل"
    if telegram_id in DUSKENDALE_COURT_TELEGRAM_IDS:
        return "دانکدایل"
    if telegram_id in HIGHGARDEN_COURT_TELEGRAM_IDS:
        return "هایگاردن"
    if telegram_id in OLDTOWN_COURT_TELEGRAM_IDS:
        return "اولد تاون"
    if telegram_id in ARBOR_COURT_TELEGRAM_IDS:
        return "آربور"
    if telegram_id in TARLY_COURT_TELEGRAM_IDS:
        return "هورن‌هیل"
    if telegram_id in WINTERFELL_COURT_TELEGRAM_IDS:
        return "وینترفل"
    if telegram_id in KARHOLD_COURT_TELEGRAM_IDS:
        return "کارهولد"
    if telegram_id in BARROWTON_COURT_TELEGRAM_IDS:
        return "باروتون"
    if telegram_id in CASTERLY_ROCK_COURT_TELEGRAM_IDS:
        return "کسترلی‌راک"
    if telegram_id in CRAKEHALL_COURT_TELEGRAM_IDS:
        return "کراکهال"
    return player.get("castle_name")


def can_manage_court(player, castle_name):
    if not player or not player.get("is_active"):
        return False
    try:
        telegram_id = int(player.get("telegram_id") or 0)
    except (TypeError, ValueError):
        telegram_id = 0
    castle = normalize_court_name(castle_name)
    # Royal appointments are strictly reserved for Aegon and Rhaenyra,
    # including when another account has global administrator privileges.
    if castle in (normalize_court_name("کینگزلندینگ"), normalize_court_name("King's Landing")):
        return telegram_id == 6523502457
    if castle in (normalize_court_name("دراگون‌استون"), normalize_court_name("Dragonstone")):
        return telegram_id == 5632444639
    if player.get("is_super_admin"):
        return True
    if castle in (normalize_court_name("دریفت‌مارک"), normalize_court_name("Driftmark")):
        return telegram_id == 7650983591
    if castle in (
        normalize_court_name("کلاوآیل"),
        normalize_court_name("کلاور آیل"),
        normalize_court_name("Claw Isle"),
    ):
        return telegram_id == 8128459841
    if castle in (
        normalize_court_name("دانکدایل"),
        normalize_court_name("دانسکندیل"),
        normalize_court_name("Duskendale"),
    ):
        return telegram_id == 6669583051
    if castle in (
        normalize_court_name("آربور"),
        normalize_court_name("The Arbor"),
        normalize_court_name("Arbor"),
    ):
        return telegram_id == 8345844522
    return (
        player.get("role") == "house_leader"
        and normalize_court_name(player.get("castle_name")) == castle
    )


def court_post_authority(post_key, castle_name):
    if post_key == "hand":
        return ["realm:delegated_executive", "realm:diplomacy", "realm:military", "realm:justice", "realm:treasury", "realm:intelligence"]
    if post_key == "ships":
        return ["realm:naval"]
    if post_key == "laws":
        return ["realm:justice"]
    if post_key == "coin":
        return ["realm:treasury"]
    if post_key == "whispers":
        return ["realm:intelligence"]
    if post_key == "army":
        return ["realm:military"]
    if post_key == "kingsguard":
        return ["realm:kingsguard"]
    if post_key == "citywatch":
        return ["realm:city_watch"]
    if post_key == "spymaster":
        return ["castle:intelligence"]
    if post_key == "commander":
        return ["castle:military"]
    if post_key == "treasurer":
        return ["castle:treasury"]
    return []


async def court_appointments_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    effective_castle = player_court_castle(player)
    castle_name = str(request.query.get("castle_name") or effective_castle or "").strip()
    if not castle_name or len(castle_name) > 150:
        return json_error("invalid_castle_name")
    if not player.get("is_super_admin") and normalize_court_name(castle_name) != normalize_court_name(effective_castle):
        return json_error("forbidden", 403)
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT post_key, appointee_name, updated_at
            FROM court_appointments
            WHERE castle_name = $1
            ORDER BY post_key
            """,
            castle_name,
        )
    posts = court_posts_for_castle(castle_name)
    appointments = {
        row["post_key"]: {
            "post_key": row["post_key"],
            "title": posts.get(row["post_key"], row["post_key"]),
            "appointee_name": row["appointee_name"],
            "updated_at": row["updated_at"].isoformat(),
            "authority": court_post_authority(row["post_key"], castle_name),
        }
        for row in rows
    }
    return web.json_response({
        "ok": True,
        "castle_name": castle_name,
        "appointments": appointments,
        "posts": posts,
        "can_manage": can_manage_court(player, castle_name),
        "sovereign_retains_final_authority": True,
    })


async def court_appointment_update_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    try:
        data = await request.json()
    except Exception:
        return json_error("invalid_json")
    effective_castle = player_court_castle(player)
    castle_name = str(data.get("castle_name") or effective_castle or "").strip()
    post_key = str(data.get("post_key") or "").strip()
    appointee_name = str(data.get("appointee_name") or "").strip()
    if not castle_name or len(castle_name) > 150 or len(appointee_name) > 150:
        return json_error("invalid_appointment")
    if not can_manage_court(player, castle_name):
        return json_error("forbidden", 403)
    posts = court_posts_for_castle(castle_name)
    if post_key not in posts:
        return json_error("invalid_court_post")
    if not appointee_name:
        async with request.app["db"].acquire() as conn:
            await conn.execute(
                "DELETE FROM court_appointments WHERE castle_name = $1 AND post_key = $2",
                castle_name, post_key,
            )
        return web.json_response({"ok": True, "removed": True, "post_key": post_key})
    async with request.app["db"].acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO court_appointments (castle_name, post_key, appointee_name, appointed_by, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (castle_name, post_key)
            DO UPDATE SET appointee_name = EXCLUDED.appointee_name,
                          appointed_by = EXCLUDED.appointed_by,
                          updated_at = NOW()
            RETURNING post_key, appointee_name, updated_at
            """,
            castle_name, post_key, appointee_name, player["id"],
        )
    return web.json_response({
        "ok": True,
        "appointment": {
            "post_key": row["post_key"],
            "title": posts[post_key],
            "appointee_name": row["appointee_name"],
            "updated_at": row["updated_at"].isoformat(),
            "authority": court_post_authority(post_key, castle_name),
        },
    })



TRAVEL_CASTLE_ALIASES = {
    "دراگون‌استون": ["دراگون‌استون", "دراگون استون", "Dragonstone", "Dragon Stone"],
    "کینگزلندینگ": ["کینگزلندینگ", "کینگز لندینگ", "King's Landing", "King’s Landing", "Kings Landing"],
    "اولدتاون": ["اولدتاون", "اولد تاون", "Oldtown", "Old Town"],
    "دریفت‌مارک": ["دریفت‌مارک", "دریفت مارک", "Driftmark"],
    "سلتگار": ["سلتگار", "کلاو آیل", "Claw Isle"],
    "دارکلین": ["دارکلین", "دانسکندیل", "Duskendale"],
    "ریوران": ["ریوران", "ریورران", "Riverrun"],
    "استون‌هج": ["استون‌هج", "استون هج", "استون هِج", "Stone Hedge"],
    "ریون‌تری‌هال": ["ریون‌تری‌هال", "ریون تری هال", "Raventree Hall"],
    "تویینز": ["تویینز", "Twins", "The Twins"],
    "وینترفل": ["وینترفل", "Winterfell"],
    "لاست هرت": ["لاست هرت", "لست هرت", "Last Hearth"],
    "کارهولد": ["کارهولد", "Karhold"],
    "باروتون": ["باروتون", "Barrowton"],
    "کسترلی‌راک": ["کسترلی‌راک", "کسترلی راک", "Casterly Rock"],
    "کرکهال": ["کرکهال", "کراکهال", "Crakehall"],
    "گلدن‌توس": ["گلدن‌توس", "گلدن توث", "Golden Tooth"],
    "های‌گاردن": ["های‌گاردن", "های گاردن", "Highgarden"],
    "هورن‌هیل": ["هورن‌هیل", "هورن هیل", "Horn Hill"],
    "آربور": ["آربور", "Arbor", "The Arbor"],
    "استورمزاند": ["استورمزاند", "استورمز اند", "Storm's End", "Storm’s End"],
    "نایت‌سانگ": ["نایت‌سانگ", "نایت سونگ", "Nightsong"],
    "قلعه سوان": ["قلعه سوان", "استون‌هلم", "Stonehelm", "House Swann"],
    "قلعه فل": ["قلعه فل", "فل‌وود هال", "Felwood", "House Fell"],
    "ایری": ["ایری", "Eyrie", "The Eyrie"],
    "ران‌استون": ["ران‌استون", "ران استون", "رانستون", "Runestone"],
    "هارتس‌هوم": ["هارتس‌هوم", "هارتس هوم", "Harte's Home", "Harte’s Home"],
    "سان‌اسپیر": ["سان‌اسپیر", "سان اسپیر", "Sunspear"],
    "یرنوود": ["یرنوود", "Yronwood"],
    "اسکای‌ریچ": ["اسکای‌ریچ", "اسکای ریچ", "Skyreach"],
    "گادزگریس": ["گادزگریس", "Godsgrace"],
    "استارفال": ["استارفال", "Starfall"],
    "پایک": ["پایک", "Pyke"],
    "ده برج": ["ده برج", "Ten Towers"],
    "بلک‌تاید": ["بلک‌تاید", "بلک تاید", "Blacktyde"],
    "گریت‌ویک": ["گریت‌ویک", "گریت ویک", "Great Wyk"],
}


TRAVEL_CHARACTER_ROSTER = {
    "دراگون‌استون": [
        "رینیرا تارگرین | Rhaenyra Targaryen",
        "دیمون تارگرین | Daemon Targaryen",
        "جیسریس ولاریون | Jacaerys Velaryon",
        "بیلا تارگرین | Baela Targaryen",
        "رینا تارگرین | Rhaena Targaryen",
        "رینیس تارگرین | Rhaenys Targaryen",
        "هیو همر | Hugh Hammer",
        "اریک کارگیل | Erryk Cargyll",
        "آدام ولاریون | Addam Velaryon",
        "سر لورنت ماربریند | Ser Lorent Marbrand",
        "سر ویلیام رویس | Ser Willam Royce",
        "سر استفون دارکلین | Ser Steffon Darklyn"
    ],
    "کینگزلندینگ": [
        "اگان دوم تارگرین | Aegon II Targaryen",
        "هلینا تارگرین | Helaena Targaryen",
        "الیسنت های‌تاور | Alicent Hightower",
        "ایموند تارگرین | Aemond Targaryen",
        "کریستون کول | Criston Cole",
        "سر لوثر لارجنت | Ser Luthor Largent",
        "اریک کارگیل | Arryk Cargyll",
        "اولف وایت | Ulf White",
        "سپتون اعظم"
    ],
    "اولدتاون": [
        "دیرون تارگرین | Daeron Targaryen",
        "اتو های‌تاور | Otto Hightower",
        "اورموند های‌تاور | Ormund Hightower",
        "سر جون روکستون | Ser Jon Roxton",
        "سر گوین های‌تاور | Ser Gwayne Hightower"
    ],
    "دریفت‌مارک": [
        "کورلیس ولاریون | Corlys Velaryon",
        "آدام ولاریون | Addam Velaryon"
    ],
    "سلتگار": [
        "بارتیموس سلتگار | Bartimos Celtigar"
    ],
    "دارکلین": [
        "ینالد دارکلین | Ynald Darklyn"
    ],
    "ریوران": [
        "اسکار تالی | Grover Tully",
        "ادموند تالی | Elmo Tully",
        "کرمیت تالی | Kermit Tully",
        "تینسا تالی | Tansy Tully"
    ],
    "استون‌هج": [
        "آموس براکن | Amos Bracken"
    ],
    "ریون‌تری‌هال": [
        "بنجیکات بلک‌وود | Benjicot Blackwood"
    ],
    "تویینز": [
        "فورست فری | Forrest Frey"
    ],
    "وینترفل": [
        "کریگان استارک | Cregan Stark",
        "ریکان استارک | Rickon Stark",
        "بنجن استارک | Benjen Stark",
        "سارا اسنو | Sara Snow"
    ],
    "لاست هرت": [
        "هارموند آمبر | Harmond Umber"
    ],
    "کارهولد": [
        "آلیس کاراستارک | Alys Karstark"
    ],
    "باروتون": [
        "رودریک داستین | Roderick Dustin"
    ],
    "کسترلی‌راک": [
        "جیسون لنیستر | Jason Lannister",
        "تایلند لنیستر | Tyland Lannister",
        "لورِن لنیستر | Loreon Lannister",
        "جُهانا لنیستر | Johanna Lannister"
    ],
    "کرکهال": [
        "کلارنت کرکهال | Clarrent Crakehall"
    ],
    "گلدن‌توس": [
        "هامفری لفورد | Humphrey Lefford"
    ],
    "های‌گاردن": [
        "لیونل تایرل | Lyonel Tyrell",
        "لوراس تایرل | Loras Tyrell",
        "لئو تایرل | Leo Tyrell",
        "جنسیا فاسوی | Jancia Fossoway"
    ],
    "هورن‌هیل": [
        "آلن تارلی | Alan Tarly"
    ],
    "آربور": [
        "گارث ردواین | Garth Redwyne"
    ],
    "استورمزاند": [
        "بوروس باراثیون | Borros Baratheon",
        "رویس باراثیون | Royce Baratheon",
        "کاساندرا باراثیون | Cassandra Baratheon"
    ],
    "نایت‌سانگ": [
        "رویس کارون | Royce Caron"
    ],
    "قلعه سوان": [
        "بایرون سوان | Byron Swann"
    ],
    "قلعه فل": [
        "ویلیس فل | Willis Fell"
    ],
    "ایری": [
        "جین آرین | Jeyne Arryn",
        "آرنولد آرین | Arnold Arryn",
        "جوفری آرین | Joffrey Arryn"
    ],
    "ران‌استون": [
        "یوربرت رویس | Yorbert Royce"
    ],
    "هارتس‌هوم": [
        "لئووین کوربری | Leowyn Corbray"
    ],
    "سان‌اسپیر": [
        "قورن مارتل | Qoren Martell",
        "آلیاندرا مارتل | Aliandra Martell",
        "کوریان مارتل | Coryanne Martell"
    ],
    "یرنوود": [
        "آندرس یرونوود | Anders Yronwood"
    ],
    "اسکای‌ریچ": [
        "فرانکلین فولر | Franklyn Fowler"
    ],
    "گادزگریس": [
        "دلون آلیرین | Delonne Allyrion"
    ],
    "استارفال": [
        "ادریک دین | Edric Dayne"
    ],
    "پایک": [
        "دالتون گریجوی | Dalton Greyjoy",
        "ورون گریجوی | Veron Greyjoy"
    ],
    "ده برج": [
        "سر هاراس هارلو | Ser Harras Harlaw"
    ],
    "بلک‌تاید": [
        "لورِن بلکتاید | Lorren Blacktyde"
    ],
    "گریت‌ویک": [
        "گورولد گودبرو | Gorold Goodbrother"
    ]
}

def canonical_travel_castle(value):
    normalized = normalize_court_name(value)
    for canonical, aliases in TRAVEL_CASTLE_ALIASES.items():
        if normalized == normalize_court_name(canonical) or any(
            normalized == normalize_court_name(alias) for alias in aliases
        ):
            return canonical
    return None


async def character_travel_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    requested_castle = str(request.query.get("castle_name") or "").strip()
    castle = canonical_travel_castle(requested_castle)
    if not castle:
        return json_error("invalid_castle_name")
    player_castle = canonical_travel_castle(player.get("castle_name"))
    can_travel = bool(player.get("is_super_admin") or player_castle == castle)
    if not can_travel:
        return json_error("forbidden", 403)
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT character_name, home_castle, current_castle, travel_type, updated_at
            FROM character_travels
            WHERE current_castle = $1 AND home_castle <> current_castle
            ORDER BY character_name
            """,
            castle,
        )
        away_rows = await conn.fetch(
            """
            SELECT character_name, home_castle, current_castle, travel_type, updated_at
            FROM character_travels
            WHERE home_castle = $1 AND current_castle <> home_castle
            ORDER BY character_name
            """,
            castle,
        )
    def travel_item(row):
        return {
            "character_name": row["character_name"],
            "home_castle": row["home_castle"],
            "current_castle": row["current_castle"],
            "destination_castle": row["current_castle"],
            "travel_type": row["travel_type"] or "temporary",
            "court_member": (row["travel_type"] or "temporary") == "permanent",
            "updated_at": row["updated_at"].isoformat(),
        }
    arrivals = [travel_item(row) for row in rows]
    return web.json_response({
        "ok": True,
        "castle_name": castle,
        "can_travel": can_travel,
        "destinations": list(TRAVEL_CASTLE_ALIASES.keys()),
        "court_members": [item for item in arrivals if item["court_member"]],
        "guests": [item for item in arrivals if not item["court_member"]],
        "away": [travel_item(row) for row in away_rows],
    })


async def character_travel_update_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    try:
        data = await request.json()
    except Exception:
        return json_error("invalid_json")
    character_name = str(data.get("character_name") or "").strip()
    home_castle = canonical_travel_castle(data.get("home_castle"))
    destination = canonical_travel_castle(data.get("destination_castle"))
    travel_type = str(data.get("travel_type") or "temporary").strip().lower()
    if travel_type not in ("temporary", "permanent"):
        return json_error("invalid_travel_type")
    player_castle = canonical_travel_castle(player.get("castle_name"))
    if not character_name or len(character_name) > 150 or not home_castle or not destination:
        return json_error("invalid_travel")
    allowed_names = TRAVEL_CHARACTER_ROSTER.get(home_castle, [])
    if character_name not in allowed_names:
        return json_error("unknown_character")
    if not player.get("is_super_admin") and player_castle != home_castle:
        return json_error("forbidden", 403)
    async with request.app["db"].acquire() as conn:
        if destination == home_castle:
            await conn.execute(
                "DELETE FROM character_travels WHERE character_name = $1 AND home_castle = $2",
                character_name, home_castle,
            )
            updated_at = None
        else:
            row = await conn.fetchrow(
                """
                INSERT INTO character_travels
                    (character_name, home_castle, current_castle, travel_type, last_travel_by, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (character_name, home_castle)
                DO UPDATE SET current_castle = EXCLUDED.current_castle,
                              travel_type = EXCLUDED.travel_type,
                              last_travel_by = EXCLUDED.last_travel_by,
                              updated_at = NOW()
                RETURNING updated_at
                """,
                character_name, home_castle, destination, travel_type, player["id"],
            )
            updated_at = row["updated_at"].isoformat()
    return web.json_response({
        "ok": True,
        "character_name": character_name,
        "home_castle": home_castle,
        "current_castle": destination,
        "travel_type": travel_type if destination != home_castle else None,
        "court_member": destination != home_castle and travel_type == "permanent",
        "returned_home": destination == home_castle,
        "updated_at": updated_at,
    })




MARRIAGE_CEREMONIES = {
    "ordinary": {"name": "معمولی", "coins": 200, "food": 150, "wine": 5, "bonus": 5, "days": 3},
    "noble": {"name": "اشرافی", "coins": 600, "food": 400, "wine": 15, "bonus": 12, "days": 6},
    "royal": {"name": "سلطنتی", "coins": 1500, "food": 1000, "wine": 40, "bonus": 22, "days": 10},
}


async def marriage_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    async with request.app["db"].acquire() as conn:
        own = await conn.fetch("""
            SELECT cp.id, cp.character_name, cp.gender, cp.spouse
            FROM character_profiles cp
            WHERE cp.owner_player_id=$1
            ORDER BY cp.character_name
        """, player["id"])
        available = await conn.fetch("""
            SELECT cp.id, cp.character_name, cp.house, p.id AS player_id,
                   p.username AS player_name, h.name AS house_name
            FROM character_profiles cp
            JOIN players p ON p.id=cp.owner_player_id AND p.is_active=TRUE
            LEFT JOIN houses h ON h.id=p.house_id
            WHERE cp.gender='female' AND p.id<>$1
              AND COALESCE(cp.spouse,'') IN ('','هنوز ازدواج نکرده','نیازمند تعیین','ثبت نشده')
              AND NOT EXISTS (SELECT 1 FROM marriages m WHERE m.bride_profile_id=cp.id OR m.groom_profile_id=cp.id)
            ORDER BY p.username, cp.character_name
        """, player["id"])
        inbox = await conn.fetch("""
            SELECT mp.id, mp.status, mp.created_at, mp.groom_profile_id,
                   gp.character_name AS groom_name, gp.house AS groom_house,
                   mp.groom_player_id, p.username AS groom_player_name
            FROM marriage_proposals mp
            JOIN character_profiles gp ON gp.id=mp.groom_profile_id
            JOIN players p ON p.id=mp.groom_player_id
            WHERE mp.bride_player_id=$1 AND mp.status='pending'
            ORDER BY mp.created_at DESC
        """, player["id"])
        outbox = await conn.fetch("""
            SELECT mp.id, mp.status, mp.created_at, bp.character_name AS bride_name,
                   p.username AS bride_player_name
            FROM marriage_proposals mp
            JOIN character_profiles bp ON bp.id=mp.bride_profile_id
            JOIN players p ON p.id=mp.bride_player_id
            WHERE mp.groom_player_id=$1
            ORDER BY mp.created_at DESC LIMIT 50
        """, player["id"])
        marriages = await conn.fetch("""
            SELECT m.*, gp.character_name AS groom_name, bp.character_name AS bride_name,
                   gh.name AS groom_house_name, bh.name AS bride_house_name
            FROM marriages m
            JOIN character_profiles gp ON gp.id=m.groom_profile_id
            JOIN character_profiles bp ON bp.id=m.bride_profile_id
            LEFT JOIN players gpl ON gpl.id=m.groom_player_id
            LEFT JOIN players bpl ON bpl.id=m.bride_player_id
            LEFT JOIN houses gh ON gh.id=gpl.house_id
            LEFT JOIN houses bh ON bh.id=bpl.house_id
            WHERE m.groom_player_id=$1 OR m.bride_player_id=$1
            ORDER BY m.created_at DESC
        """, player["id"])
        gifts = await conn.fetch("""
            SELECT wg.id, wg.item_name, wg.quantity, wg.created_at,
                   p.username AS sender_name, wi.marriage_id
            FROM wedding_gifts wg
            JOIN wedding_invitations wi ON wi.id=wg.invitation_id
            JOIN players p ON p.id=wg.sender_player_id
            JOIN marriages m ON m.id=wi.marriage_id
            WHERE m.groom_player_id=$1 OR m.bride_player_id=$1
            ORDER BY wg.created_at DESC LIMIT 200
        """, player["id"])
        invitations = await conn.fetch("""
            SELECT wi.id, wi.response, wi.created_at, m.id AS marriage_id,
                   gp.character_name AS groom_name, bp.character_name AS bride_name,
                   m.ceremony_level, m.ceremony_at, g.username AS groom_player_name,
                   b.username AS bride_player_name
            FROM wedding_invitations wi
            JOIN marriages m ON m.id=wi.marriage_id
            JOIN character_profiles gp ON gp.id=m.groom_profile_id
            JOIN character_profiles bp ON bp.id=m.bride_profile_id
            JOIN players g ON g.id=m.groom_player_id
            JOIN players b ON b.id=m.bride_player_id
            WHERE wi.invited_player_id=$1
            ORDER BY wi.created_at DESC LIMIT 100
        """, player["id"])
    def iso(row, key):
        value=row.get(key)
        return value.isoformat() if value else None
    def clean(row, dates=()):
        item=dict(row)
        for key in dates:
            item[key]=iso(row,key)
        return item
    return web.json_response({
        "ok": True, "my_characters":[dict(r) for r in own],
        "available_brides":[dict(r) for r in available],
        "incoming":[clean(r,("created_at",)) for r in inbox],
        "outgoing":[clean(r,("created_at",)) for r in outbox],
        "marriages":[clean(r,("created_at","ceremony_at","satisfaction_expires_at")) for r in marriages],
        "invitations":[clean(r,("created_at","ceremony_at")) for r in invitations],
        "gifts":[clean(r,("created_at",)) for r in gifts],
        "ceremonies": MARRIAGE_CEREMONIES,
    })


async def marriage_proposal_create_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    try:
        data=await request.json()
        groom_id=int(data.get("groom_profile_id",0))
        bride_id=int(data.get("bride_profile_id",0))
    except (ValueError,TypeError,Exception):
        return json_error("invalid_proposal")
    if groom_id<=0 or bride_id<=0 or groom_id==bride_id:
        return json_error("invalid_proposal")
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            groom=await conn.fetchrow("""
                SELECT id,owner_player_id,character_name,gender,spouse
                FROM character_profiles WHERE id=$1 FOR UPDATE
            """,groom_id)
            bride=await conn.fetchrow("""
                SELECT id,owner_player_id,character_name,gender,spouse
                FROM character_profiles WHERE id=$1 FOR UPDATE
            """,bride_id)
            if not groom or groom["owner_player_id"]!=player["id"]:
                return json_error("groom_not_owned",403)
            if not bride or bride["gender"]!="female" or groom["gender"]!="male":
                return json_error("male_to_female_only",403)
            if bride["owner_player_id"]==player["id"]:
                return json_error("cannot_propose_to_self")
            if not bride["owner_player_id"] or not await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM players WHERE id=$1 AND is_active=TRUE)",bride["owner_player_id"]
            ):
                return json_error("bride_unavailable")
            if str(groom["spouse"] or "") not in ("","هنوز ازدواج نکرده","نیازمند تعیین","ثبت نشده") or str(bride["spouse"] or "") not in ("","هنوز ازدواج نکرده","نیازمند تعیین","ثبت نشده"):
                return json_error("character_already_married")
            exists=await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM marriages WHERE groom_profile_id=ANY($1::bigint[]) OR bride_profile_id=ANY($1::bigint[]))
            """,[groom_id,bride_id])
            if exists:
                return json_error("character_already_married")
            pending=await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM marriage_proposals
                WHERE groom_profile_id=$1 AND bride_profile_id=$2 AND status='pending')
            """,groom_id,bride_id)
            if pending:
                return json_error("proposal_already_pending")
            row=await conn.fetchrow("""
                INSERT INTO marriage_proposals
                    (groom_player_id,bride_player_id,groom_profile_id,bride_profile_id)
                VALUES ($1,$2,$3,$4) RETURNING id
            """,player["id"],bride["owner_player_id"],groom_id,bride_id)
    return web.json_response({"ok":True,"proposal_id":int(row["id"])})


async def marriage_proposal_respond_handler(request):
    player=await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized",401)
    try:
        proposal_id=int(request.match_info["proposal_id"])
        data=await request.json()
        decision=str(data.get("decision","")).strip()
    except Exception:
        return json_error("invalid_response")
    if decision not in ("accept","reject"):
        return json_error("invalid_response")
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            proposal=await conn.fetchrow("""
                SELECT * FROM marriage_proposals WHERE id=$1 FOR UPDATE
            """,proposal_id)
            if not proposal or proposal["bride_player_id"]!=player["id"] or proposal["status"]!="pending":
                return json_error("proposal_not_found_or_not_yours",404)
            if decision=="reject":
                await conn.execute("UPDATE marriage_proposals SET status='rejected',responded_at=NOW() WHERE id=$1",proposal_id)
                return web.json_response({"ok":True,"status":"rejected"})
            groom=await conn.fetchrow("SELECT character_name FROM character_profiles WHERE id=$1 FOR UPDATE",proposal["groom_profile_id"])
            bride=await conn.fetchrow("SELECT character_name FROM character_profiles WHERE id=$1 FOR UPDATE",proposal["bride_profile_id"])
            if not groom or not bride:
                return json_error("character_not_found")
            already=await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM marriages WHERE groom_profile_id=ANY($1::bigint[]) OR bride_profile_id=ANY($1::bigint[]))
            """,[proposal["groom_profile_id"],proposal["bride_profile_id"]])
            if already:
                return json_error("character_already_married")
            marriage=await conn.fetchrow("""
                INSERT INTO marriages (groom_player_id,bride_player_id,groom_profile_id,bride_profile_id)
                VALUES ($1,$2,$3,$4) RETURNING id
            """,proposal["groom_player_id"],proposal["bride_player_id"],proposal["groom_profile_id"],proposal["bride_profile_id"])
            await conn.execute("""
                UPDATE character_profiles SET spouse=$1,updated_at=NOW() WHERE id=$2
            """,bride["character_name"],proposal["groom_profile_id"])
            await conn.execute("""
                UPDATE character_profiles SET spouse=$1,updated_at=NOW() WHERE id=$2
            """,groom["character_name"],proposal["bride_profile_id"])
            await conn.execute("UPDATE marriage_proposals SET status='accepted',responded_at=NOW() WHERE id=$1",proposal_id)
    return web.json_response({"ok":True,"status":"accepted","marriage_id":int(marriage["id"])})


async def marriage_ceremony_handler(request):
    player=await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized",401)
    try:
        marriage_id=int(request.match_info["marriage_id"])
        data=await request.json()
        level=str(data.get("level","")).strip()
    except Exception:
        return json_error("invalid_ceremony")
    ceremony=MARRIAGE_CEREMONIES.get(level)
    if not ceremony:
        return json_error("invalid_ceremony")
    import json
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            marriage=await conn.fetchrow("""
                SELECT * FROM marriages WHERE id=$1 FOR UPDATE
            """,marriage_id)
            if not marriage or player["id"] not in (marriage["groom_player_id"],marriage["bride_player_id"]):
                return json_error("marriage_not_found_or_not_yours",404)
            if marriage["ceremony_level"]:
                return json_error("ceremony_already_chosen")
            groom_house_id=await conn.fetchval("SELECT house_id FROM players WHERE id=$1",marriage["groom_player_id"])
            bride_house_id=await conn.fetchval("SELECT house_id FROM players WHERE id=$1",marriage["bride_player_id"])
            if not groom_house_id:
                return json_error("groom_has_no_house")
            house=await conn.fetchrow("SELECT resources,game_state FROM houses WHERE id=$1 FOR UPDATE",groom_house_id)
            if not house:
                return json_error("house_not_found")
            resources=_canonical_house_resources(_json_object(house["resources"]),_json_object(house["game_state"]).get("resources"))
            special=resources.get("specialGoods") or {}
            if int(resources.get("coins",0) or 0)<ceremony["coins"] or int(resources.get("food",0) or 0)<ceremony["food"] or int(special.get("wine",0) or 0)<ceremony["wine"]:
                return json_error("insufficient_ceremony_resources")
            resources["coins"]=int(resources.get("coins",0))-ceremony["coins"]
            resources["food"]=int(resources.get("food",0))-ceremony["food"]
            special["wine"]=int(special.get("wine",0))-ceremony["wine"]
            resources["specialGoods"]=special
            house_resources={
                "wood":resources.get("wood",0),"stone":resources.get("stone",0),
                "iron":resources.get("iron",0),"coins":resources["coins"],
                "food":resources["food"],"subjects":resources.get("subjects",0),
                "warhorses":resources.get("warhorses",0),
                "fur":special.get("fur",0),"wool":special.get("wool",0),
                "wine":special["wine"],"spice":special.get("spice",0),
                "salt":special.get("salt",0),"black_iron":special.get("blackIron",0),
            }
            state=_json_object(house["game_state"])
            state["resources"]=resources
            bonus_expires=await conn.fetchval(
                "SELECT (NOW()+($1::text || ' days')::interval)",ceremony["days"]
            )
            state["publicSatisfactionBonus"]=ceremony["bonus"]
            state["publicSatisfactionBonusExpiresAt"]=bonus_expires.isoformat()
            await conn.execute("""
                UPDATE houses SET resources=$1::jsonb,game_state=$2::jsonb,game_state_updated_at=NOW()
                WHERE id=$3
            """,json.dumps(house_resources,ensure_ascii=False),json.dumps(state,ensure_ascii=False),groom_house_id)
            if bride_house_id and int(bride_house_id)!=int(groom_house_id):
                bride_state_row=await conn.fetchrow(
                    "SELECT game_state FROM houses WHERE id=$1 FOR UPDATE",bride_house_id
                )
                if bride_state_row:
                    bride_state=_json_object(bride_state_row["game_state"])
                    bride_state["publicSatisfactionBonus"]=ceremony["bonus"]
                    bride_state["publicSatisfactionBonusExpiresAt"]=bonus_expires.isoformat()
                    await conn.execute(
                        "UPDATE houses SET game_state=$1::jsonb,game_state_updated_at=NOW() WHERE id=$2",
                        json.dumps(bride_state,ensure_ascii=False),bride_house_id
                    )
            await conn.execute("""
                UPDATE marriages SET ceremony_level=$1,ceremony_at=NOW(),
                    satisfaction_bonus=$2,
                    satisfaction_expires_at=NOW()+($3::text || ' days')::interval
                WHERE id=$4
            """,level,ceremony["bonus"],ceremony["days"],marriage_id)
    return web.json_response({"ok":True,"ceremony":ceremony,"message":"ceremony_confirmed"})


async def wedding_invite_all_handler(request):
    player=await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized",401)
    try:
        marriage_id=int(request.match_info["marriage_id"])
    except ValueError:
        return json_error("invalid_marriage_id")
    async with request.app["db"].acquire() as conn:
        marriage=await conn.fetchrow("SELECT * FROM marriages WHERE id=$1",marriage_id)
        if not marriage or player["id"] not in (marriage["groom_player_id"],marriage["bride_player_id"]):
            return json_error("marriage_not_found_or_not_yours",404)
        if not marriage["ceremony_level"]:
            return json_error("choose_ceremony_first")
        result=await conn.execute("""
            INSERT INTO wedding_invitations (marriage_id,invited_player_id)
            SELECT $1,id FROM players
            WHERE is_active=TRUE AND id NOT IN ($2,$3)
            ON CONFLICT (marriage_id,invited_player_id) DO NOTHING
        """,marriage_id,marriage["groom_player_id"],marriage["bride_player_id"])
    return web.json_response({"ok":True,"message":"all_players_invited","result":result})


async def wedding_invitation_respond_handler(request):
    player=await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized",401)
    try:
        invitation_id=int(request.match_info["invitation_id"])
        data=await request.json()
        response=str(data.get("response","")).strip()
    except Exception:
        return json_error("invalid_response")
    if response not in ("attending","declined"):
        return json_error("invalid_response")
    async with request.app["db"].acquire() as conn:
        result=await conn.execute("""
            UPDATE wedding_invitations SET response=$1
            WHERE id=$2 AND invited_player_id=$3
        """,response,invitation_id,player["id"])
    if result.endswith(" 0"):
        return json_error("invitation_not_found",404)
    return web.json_response({"ok":True})


async def wedding_gift_handler(request):
    player=await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized",401)
    if not player.get("house_id"):
        return json_error("player_has_no_house",403)
    try:
        invitation_id=int(request.match_info["invitation_id"])
        data=await request.json()
        item=str(data.get("item_name","")).strip()
        quantity=int(data.get("quantity",0))
    except Exception:
        return json_error("invalid_gift")
    if item not in TRADE_GOODS or quantity<1 or quantity>1000000:
        return json_error("invalid_gift")
    import json
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            invite=await conn.fetchrow("""
                SELECT wi.*,m.groom_player_id,m.bride_player_id,m.ceremony_level,
                       gp.character_name AS groom_name,bp.character_name AS bride_name
                FROM wedding_invitations wi JOIN marriages m ON m.id=wi.marriage_id
                JOIN character_profiles gp ON gp.id=m.groom_profile_id
                JOIN character_profiles bp ON bp.id=m.bride_profile_id
                WHERE wi.id=$1 AND wi.invited_player_id=$2 FOR UPDATE OF wi
            """,invitation_id,player["id"])
            if not invite:
                return json_error("invitation_not_found",404)
            if invite["response"]=="declined":
                return json_error("invitation_declined")
            if not invite["ceremony_level"]:
                return json_error("ceremony_not_selected")
            groom_house_id=await conn.fetchval("SELECT house_id FROM players WHERE id=$1",invite["groom_player_id"])
            if not groom_house_id:
                return json_error("groom_has_no_house")
            if int(player["house_id"])==int(groom_house_id):
                await conn.execute(
                    "INSERT INTO wedding_gifts (invitation_id,sender_player_id,item_name,quantity) VALUES ($1,$2,$3,$4)",
                    invitation_id,player["id"],item,quantity
                )
                return web.json_response({"ok":True,"message":"gift_recorded_within_same_house"})
            guest_house=await conn.fetchrow("SELECT resources,game_state FROM houses WHERE id=$1 FOR UPDATE",player["house_id"])
            target_house=await conn.fetchrow("SELECT resources,game_state FROM houses WHERE id=$1 FOR UPDATE",groom_house_id)
            if not guest_house or not target_house:
                return json_error("house_not_found")
            guest=_canonical_house_resources(_json_object(guest_house["resources"]),_json_object(guest_house["game_state"]).get("resources"))
            target=_canonical_house_resources(_json_object(target_house["resources"]),_json_object(target_house["game_state"]).get("resources"))
            mapping={"چوب":("wood",None),"سنگ":("stone",None),"آهن":("iron",None),"غذا":("food",None),"اسب جنگی":("warhorses",None),"خز":("specialGoods","fur"),"پشم":("specialGoods","wool"),"شراب":("specialGoods","wine"),"ادویه":("specialGoods","spice"),"آهن سیاه":("specialGoods","blackIron"),"نمک":("specialGoods","salt")}
            key,sub=mapping[item]
            guest_bucket=guest[key] if sub else guest
            target_bucket=target[key] if sub else target
            available=int(guest_bucket.get(sub,0) if sub else guest_bucket.get(key,0) or 0)
            if available<quantity:
                return json_error("insufficient_gift_stock")
            if sub:
                guest_bucket[sub]=available-quantity
                target_bucket[sub]=int(target_bucket.get(sub,0) or 0)+quantity
            else:
                guest[key]=available-quantity
                target[key]=int(target.get(key,0) or 0)+quantity
            def storage(r):
                sp=r.get("specialGoods") or {}
                return {"wood":r.get("wood",0),"stone":r.get("stone",0),"iron":r.get("iron",0),
                    "coins":r.get("coins",0),"food":r.get("food",0),"subjects":r.get("subjects",0),
                    "warhorses":r.get("warhorses",0),"fur":sp.get("fur",0),"wool":sp.get("wool",0),
                    "wine":sp.get("wine",0),"spice":sp.get("spice",0),"salt":sp.get("salt",0),
                    "black_iron":sp.get("blackIron",0)}
            gs=_json_object(guest_house["game_state"]);ts=_json_object(target_house["game_state"])
            gs["resources"]=guest;ts["resources"]=target
            await conn.execute("UPDATE houses SET resources=$1::jsonb,game_state=$2::jsonb,game_state_updated_at=NOW() WHERE id=$3",
                json.dumps(storage(guest),ensure_ascii=False),json.dumps(gs,ensure_ascii=False),player["house_id"])
            await conn.execute("UPDATE houses SET resources=$1::jsonb,game_state=$2::jsonb,game_state_updated_at=NOW() WHERE id=$3",
                json.dumps(storage(target),ensure_ascii=False),json.dumps(ts,ensure_ascii=False),groom_house_id)
            await conn.execute("INSERT INTO wedding_gifts (invitation_id,sender_player_id,item_name,quantity) VALUES ($1,$2,$3,$4)",
                invitation_id,player["id"],item,quantity)
    return web.json_response({"ok":True,"message":"gift_sent"})




async def family_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    if not player.get("house_id"):
        return web.json_response({"ok": True, "house": None, "members": [], "candidates": [], "can_manage": False})
    async with request.app["db"].acquire() as conn:
        house = await conn.fetchrow("SELECT id, name, castle, sigil FROM houses WHERE id = $1", player["house_id"])
        members = await conn.fetch("""
            SELECT id, username, role FROM players
            WHERE house_id = $1 AND is_active = TRUE
            ORDER BY CASE WHEN role = 'house_leader' THEN 0 ELSE 1 END, username
        """, player["house_id"])
        candidates = await conn.fetch("""
            SELECT p.id, p.username, h.name AS house_name FROM players p
            LEFT JOIN houses h ON h.id = p.house_id
            WHERE p.is_active = TRUE AND p.house_id IS DISTINCT FROM $1
            ORDER BY p.username
        """, player["house_id"])
    can_manage = player["role"] == "house_leader" or (
        player["role"] == "admin" and player.get("is_super_admin")
    )
    return web.json_response({
        "ok": True, "house": dict(house) if house else None,
        "members": [dict(row) for row in members],
        "candidates": [dict(row) for row in candidates] if can_manage else [],
        "can_manage": can_manage, "current_player_id": player["id"],
    })


async def family_add_member_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    can_manage = player["role"] == "house_leader" or (
        player["role"] == "admin" and player.get("is_super_admin")
    )
    if not can_manage or not player.get("house_id"):
        return json_error("forbidden", 403)
    try:
        target_id = int(request.match_info["player_id"])
    except (ValueError, TypeError):
        return json_error("invalid_player_id")
    async with request.app["db"].acquire() as conn:
        target = await conn.fetchrow("SELECT id, is_active, is_super_admin FROM players WHERE id = $1", target_id)
        if not target or not target["is_active"]:
            return json_error("player_not_found", 404)
        if target["is_super_admin"]:
            return json_error("protected_account", 403)
        await conn.execute("UPDATE players SET house_id = $1 WHERE id = $2", player["house_id"], target_id)
    return web.json_response({"ok": True, "message": "member_assigned"})


async def family_remove_member_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    can_manage = player["role"] == "house_leader" or (
        player["role"] == "admin" and player.get("is_super_admin")
    )
    if not can_manage or not player.get("house_id"):
        return json_error("forbidden", 403)
    try:
        target_id = int(request.match_info["player_id"])
    except (ValueError, TypeError):
        return json_error("invalid_player_id")
    if target_id == int(player["id"]):
        return json_error("cannot_remove_self", 400)
    async with request.app["db"].acquire() as conn:
        result = await conn.execute("""
            UPDATE players SET house_id = NULL
            WHERE id = $1 AND house_id = $2 AND is_super_admin = FALSE
        """, target_id, player["house_id"])
    if result.endswith(" 0"):
        return json_error("member_not_found", 404)
    return web.json_response({"ok": True, "message": "member_removed"})


async def admin_update_player_telegram_id_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    try:
        player_id = int(request.match_info["player_id"])
        data = await request.json()
        raw_id = str(data.get("telegram_id", "")).strip()
    except (ValueError, TypeError):
        return json_error("invalid_request")
    if not raw_id.isdigit():
        return json_error("invalid_telegram_id")
    telegram_id = int(raw_id)
    if telegram_id <= 0 or telegram_id > 9223372036854775807:
        return json_error("invalid_telegram_id")
    try:
        async with request.app["db"].acquire() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(739201847)")
                target = await conn.fetchrow(
                    "SELECT id, is_super_admin FROM players WHERE id = $1 FOR UPDATE",
                    player_id,
                )
                if not target:
                    return json_error("player_not_found", 404)
                if target["is_super_admin"] and player_id != int(admin["id"]):
                    return json_error("protected_account", 403)
                updated = await conn.fetchrow(
                    "UPDATE players SET telegram_id = $1 WHERE id = $2 RETURNING id, username, telegram_id",
                    telegram_id, player_id,
                )
        return web.json_response({"ok": True, "player": dict(updated)})
    except asyncpg.UniqueViolationError:
        return json_error("telegram_id_exists", 409)


async def admin_set_player_active_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    try:
        player_id = int(request.match_info["player_id"])
        data = await request.json()
        active = data.get("is_active")
        if not isinstance(active, bool):
            return json_error("invalid_active_status")
    except (ValueError, TypeError):
        return json_error("invalid_request")
    if player_id == int(admin["id"]) and not active:
        return json_error("cannot_ban_self", 400)
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            target = await conn.fetchrow(
                "SELECT id, is_super_admin FROM players WHERE id = $1 FOR UPDATE",
                player_id,
            )
            if not target:
                return json_error("player_not_found", 404)
            if target["is_super_admin"]:
                return json_error("protected_account", 403)
            await conn.execute(
                "UPDATE players SET is_active = $1 WHERE id = $2",
                active, player_id,
            )
            if not active:
                await conn.execute(
                    "UPDATE player_sessions SET revoked_at = NOW() WHERE player_id = $1 AND revoked_at IS NULL",
                    player_id,
                )
    return web.json_response({"ok": True, "is_active": active})


async def admin_update_player_role_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    try:
        target_id = int(request.match_info["player_id"])
        data = await request.json()
    except (ValueError, TypeError):
        return json_error("invalid_request")
    role = str(data.get("role", "")).strip()
    if role not in ("player", "house_leader", "treasurer", "admin"):
        return json_error("invalid_role")
    async with request.app["db"].acquire() as conn:
        target = await conn.fetchrow("SELECT id, is_super_admin FROM players WHERE id = $1", target_id)
        if not target:
            return json_error("player_not_found", 404)
        if target["is_super_admin"] and role != "admin":
            return json_error("protected_account", 403)
        if role == "admin" and not target["is_super_admin"]:
            return json_error("admin_role_restricted", 403)
        updated = await conn.fetchrow(
            "UPDATE players SET role = $1 WHERE id = $2 RETURNING id, username, role",
            role, target_id,
        )
    return web.json_response({"ok": True, "player": dict(updated)})


async def me_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    install_id = request.headers.get("X-Game-Install-ID", "").strip()[:80] or None
    token = get_bearer_token(request)
    if token:
        ip_address = (
            request.headers.get("X-Real-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote
        )
        ip_address = str(ip_address)[:64] if ip_address else None
        user_agent = request.headers.get("User-Agent", "")[:1000] or None
        async with request.app["db"].acquire() as conn:
            await conn.execute(
                """
                UPDATE player_sessions
                SET install_id = COALESCE($1, install_id),
                    ip_address = COALESCE($2, ip_address),
                    user_agent = COALESCE($3, user_agent)
                WHERE session_token_hash = $4 AND revoked_at IS NULL
                """,
                install_id, ip_address, user_agent, hash_session_token(token),
            )
    return web.json_response({"ok": True, "player": player})



async def military_requests_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    async with request.app["db"].acquire() as conn:
        profiles = await conn.fetch("""
            SELECT cp.id, cp.character_name, cp.title, cp.location, cp.house, cp.warfare,
                   cp.owner_player_id, COALESCE(p.house_id, h.id) AS owner_house_id
            FROM character_profiles cp
            LEFT JOIN players p ON p.id = cp.owner_player_id
            LEFT JOIN houses h ON h.name = cp.house
            WHERE cp.owner_player_id IS NOT NULL OR h.id IS NOT NULL
            ORDER BY cp.character_name
        """)
        requests = await conn.fetch("""
            SELECT m.*, s.username AS sender_name, r.username AS recipient_name
            FROM military_campaigns m JOIN players s ON s.id=m.sender_player_id
            LEFT JOIN players r ON r.id=m.commander_player_id
            WHERE m.sender_player_id=$1 OR m.commander_player_id=$1
            ORDER BY m.created_at DESC LIMIT 100
        """, player["id"])
    request_items = []
    for item in requests:
        value = dict(item)
        for field in ("created_at", "responded_at"):
            if value.get(field):
                value[field] = value[field].isoformat()
        request_items.append(value)
    return web.json_response({"ok":True,"profiles":[dict(x) for x in profiles],
        "requests":request_items,"player_id":player["id"],"username":player["username"],"house_id":player.get("house_id")})


async def military_campaign_create_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    try:
        data=await request.json()
        count=int(data.get("count",0)); kind=str(data.get("commander_type","self"))
        mission=str(data.get("mission","attack")); target=str(data.get("target") or "").strip() or None
        target_by_commander=bool(data.get("target_by_commander",False))
        profile_id=int(data["profile_id"]) if data.get("profile_id") not in (None,"") else None
    except (ValueError,TypeError):
        return json_error("invalid_campaign")
    if count<1 or count>100000000 or kind not in {"self","member","hero","external"}:
        return json_error("invalid_campaign")
    if mission not in {"attack","travel","aid","defend","scout"}:
        return json_error("invalid_mission")
    if target_by_commander: target=None
    if target and len(target)>150: return json_error("invalid_target")
    commander_id=player["id"]; commander_name=player["username"]
    if kind!="self":
        if not profile_id: return json_error("commander_required")
        async with request.app["db"].acquire() as conn:
            profile=await conn.fetchrow("""
                SELECT cp.id,cp.character_name,cp.owner_player_id,cp.warfare,
                       COALESCE(p.house_id,h.id) AS owner_house_id
                FROM character_profiles cp
                LEFT JOIN players p ON p.id=cp.owner_player_id
                LEFT JOIN houses h ON h.name=cp.house
                WHERE cp.id=$1
            """,profile_id)
        if not profile: return json_error("commander_not_found",404)
        if kind == "external" and not profile["owner_player_id"]:
            return json_error("foreign_commander_must_be_player_owned",400)
        if kind in {"member","hero"} and profile["owner_house_id"]!=player.get("house_id"):
            return json_error("commander_not_in_house",403)
        if kind == "external" and profile["owner_house_id"] == player.get("house_id"):
            return json_error("external_commander_must_be_from_another_house",400)
        if kind=="hero" and int(profile["warfare"] or 0)<70: return json_error("commander_not_qualified")
        commander_id=profile["owner_player_id"] or player["id"]; commander_name=profile["character_name"]
    status="pending_commander" if kind=="external" else ("awaiting_destination" if not target else "dispatched")
    async with request.app["db"].acquire() as conn:
        row=await conn.fetchrow("""
            INSERT INTO military_campaigns
            (sender_player_id,sender_house_id,commander_player_id,commander_profile_id,commander_name,
             commander_type,target,target_by_commander,mission,troop_count,status)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            RETURNING id,status,target,mission,troop_count,commander_name
        """,player["id"],player.get("house_id"),commander_id,profile_id,commander_name,kind,
             target,target_by_commander,mission,count,status)
    return web.json_response({"ok":True,"campaign":dict(row)})


async def military_campaign_respond_handler(request):
    player=await get_authenticated_player(request)
    if not player or not player.get("is_active"): return json_error("unauthorized",401)
    try:
        campaign_id=int(request.match_info["campaign_id"]); decision=str((await request.json()).get("decision",""))
    except (ValueError,TypeError): return json_error("invalid_response")
    if decision not in {"accept","reject"}: return json_error("invalid_response")
    async with request.app["db"].acquire() as conn:
        row=await conn.fetchrow("""
            UPDATE military_campaigns SET status=CASE WHEN $1='accept'
              THEN CASE WHEN target_by_commander OR target IS NULL THEN 'awaiting_destination' ELSE 'dispatched' END
              ELSE 'rejected' END,responded_at=NOW()
            WHERE id=$2 AND commander_player_id=$3 AND status='pending_commander'
            RETURNING id,status,target,mission,troop_count
        """,decision,campaign_id,player["id"])
    if not row: return json_error("request_not_found_or_already_answered",404)
    return web.json_response({"ok":True,"campaign":dict(row)})


async def military_campaign_destination_handler(request):
    player=await get_authenticated_player(request)
    if not player or not player.get("is_active"): return json_error("unauthorized",401)
    try:
        campaign_id=int(request.match_info["campaign_id"]); target=str((await request.json()).get("target","")).strip()
    except (ValueError,TypeError): return json_error("invalid_target")
    if not target or len(target)>150: return json_error("invalid_target")
    async with request.app["db"].acquire() as conn:
        row=await conn.fetchrow("""
            UPDATE military_campaigns SET target=$1,status='dispatched'
            WHERE id=$2 AND commander_player_id=$3 AND status='awaiting_destination'
            RETURNING id,status,target,mission,troop_count
        """,target,campaign_id,player["id"])
    if not row: return json_error("campaign_not_waiting_for_destination",404)
    return web.json_response({"ok":True,"campaign":dict(row)})


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
                SELECT p.id, p.username, p.telegram_id, p.role, p.house_id, p.castle_name,
                       h.name AS house_name, p.is_active, p.is_super_admin,
                       ls.ip_address AS last_ip_address, ls.user_agent AS last_user_agent,
                       ls.install_id AS last_install_id,
                       ls.created_at AS last_login_at,
                       COALESCE((SELECT COUNT(DISTINCT s2.player_id)
                                 FROM player_sessions s2
                                 WHERE s2.ip_address = ls.ip_address
                                   AND s2.created_at > NOW() - INTERVAL '30 days'), 0) AS ip_account_count,
                       COALESCE((SELECT COUNT(DISTINCT s3.player_id)
                                 FROM player_sessions s3
                                 WHERE s3.install_id = ls.install_id
                                   AND s3.install_id IS NOT NULL), 0) AS install_account_count,
                       COALESCE((SELECT json_agg(json_build_object('id', linked.id, 'username', linked.username) ORDER BY linked.username)
                                 FROM (
                                   SELECT DISTINCT p2.id, p2.username
                                   FROM player_sessions s3
                                   JOIN players p2 ON p2.id = s3.player_id
                                   WHERE s3.install_id = ls.install_id
                                     AND ls.install_id IS NOT NULL
                                 ) linked), '[]'::json) AS install_accounts
                FROM players p
                LEFT JOIN houses h ON h.id = p.house_id
                LEFT JOIN LATERAL (
                    SELECT ip_address, user_agent, install_id, created_at
                    FROM player_sessions s
                    WHERE s.player_id = p.id
                    ORDER BY s.created_at DESC
                    LIMIT 1
                ) ls ON TRUE
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
                       h.name AS house_name, p.is_active, p.is_super_admin,
                       ls.ip_address AS last_ip_address, ls.user_agent AS last_user_agent,
                       ls.install_id AS last_install_id,
                       ls.created_at AS last_login_at,
                       COALESCE((SELECT COUNT(DISTINCT s2.player_id)
                                 FROM player_sessions s2
                                 WHERE s2.ip_address = ls.ip_address
                                   AND s2.created_at > NOW() - INTERVAL '30 days'), 0) AS ip_account_count,
                       COALESCE((SELECT COUNT(DISTINCT s3.player_id)
                                 FROM player_sessions s3
                                 WHERE s3.install_id = ls.install_id
                                   AND s3.install_id IS NOT NULL), 0) AS install_account_count,
                       COALESCE((SELECT json_agg(json_build_object('id', linked.id, 'username', linked.username) ORDER BY linked.username)
                                 FROM (
                                   SELECT DISTINCT p2.id, p2.username
                                   FROM player_sessions s3
                                   JOIN players p2 ON p2.id = s3.player_id
                                   WHERE s3.install_id = ls.install_id
                                     AND ls.install_id IS NOT NULL
                                 ) linked), '[]'::json) AS install_accounts
                FROM players p
                LEFT JOIN houses h ON h.id = p.house_id
                LEFT JOIN LATERAL (
                    SELECT ip_address, user_agent, install_id, created_at
                    FROM player_sessions s
                    WHERE s.player_id = p.id
                    ORDER BY s.created_at DESC
                    LIMIT 1
                ) ls ON TRUE
                ORDER BY p.id DESC
                LIMIT $1 OFFSET $2
                """,
                per_page, offset,
            )

    pages = max(1, (total + per_page - 1) // per_page)
    players = []
    for row in rows:
        item = dict(row)
        if item.get("last_login_at") is not None:
            item["last_login_at"] = item["last_login_at"].isoformat()
        players.append(item)
    return web.json_response({
        "ok": True,
        "players": players,
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
    })


async def admin_device_groups_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch("""
            WITH account_sessions AS (
                SELECT install_id, player_id,
                       COUNT(*) AS session_count,
                       MIN(created_at) AS first_login_at,
                       MAX(created_at) AS last_login_at
                FROM player_sessions
                WHERE install_id IS NOT NULL AND install_id <> ''
                GROUP BY install_id, player_id
            )
            SELECT a.install_id,
                   COUNT(*) AS account_count,
                   SUM(a.session_count) AS session_count,
                   MIN(a.first_login_at) AS first_seen_at,
                   MAX(a.last_login_at) AS last_seen_at,
                   json_agg(json_build_object(
                       'id', p.id,
                       'username', p.username,
                       'telegram_id', p.telegram_id,
                       'last_login_at', a.last_login_at,
                       'session_count', a.session_count
                   ) ORDER BY p.username) AS accounts
            FROM account_sessions a
            JOIN players p ON p.id = a.player_id
            GROUP BY a.install_id
            HAVING COUNT(*) > 1
            ORDER BY MAX(a.last_login_at) DESC
        """)
    groups = []
    for row in rows:
        item = dict(row)
        item["device_key"] = str(item.pop("install_id"))[-8:]
        for field in ("first_seen_at", "last_seen_at"):
            if item.get(field) is not None:
                item[field] = item[field].isoformat()
        accounts = item.get("accounts") or []
        if isinstance(accounts, str):
            try:
                accounts = json.loads(accounts)
            except (TypeError, ValueError):
                accounts = []
        if not isinstance(accounts, list):
            accounts = []
        for account in accounts:
            if not isinstance(account, dict):
                continue
            last_login_at = account.get("last_login_at")
            if hasattr(last_login_at, "isoformat"):
                account["last_login_at"] = last_login_at.isoformat()
        item["accounts"] = [account for account in accounts if isinstance(account, dict)]
        groups.append(item)
    return web.json_response({"ok": True, "groups": groups, "device_count": len(groups),
                              "account_count": len({a["id"] for g in groups for a in g["accounts"]})})


async def admin_login_requests_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch("""
            SELECT r.telegram_id, r.telegram_username, r.first_name, r.last_name,
                   r.first_seen_at, r.last_seen_at, r.attempt_count
            FROM telegram_login_requests r
            LEFT JOIN players p ON p.telegram_id = r.telegram_id
            WHERE p.id IS NULL
            ORDER BY r.last_seen_at DESC
            LIMIT 100
        """)
    requests = []
    for row in rows:
        item = dict(row)
        for field in ("first_seen_at", "last_seen_at"):
            if item.get(field) is not None:
                item[field] = item[field].isoformat()
        requests.append(item)
    return web.json_response({"ok": True, "requests": requests})


async def admin_assign_login_request_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    try:
        telegram_id = int(request.match_info["telegram_id"])
        data = await request.json()
        player_id = int(data.get("player_id", 0))
    except (ValueError, TypeError):
        return json_error("invalid_request")
    if telegram_id <= 0 or player_id <= 0:
        return json_error("invalid_request")
    try:
        async with request.app["db"].acquire() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(739201847)")
                pending = await conn.fetchrow(
                    "SELECT telegram_id FROM telegram_login_requests WHERE telegram_id = $1 FOR UPDATE",
                    telegram_id,
                )
                if not pending:
                    return json_error("login_request_not_found", 404)
                target = await conn.fetchrow(
                    "SELECT id, username, is_active, is_super_admin FROM players WHERE id = $1 FOR UPDATE",
                    player_id,
                )
                if not target:
                    return json_error("player_not_found", 404)
                if not target["is_active"]:
                    return json_error("account_disabled", 403)
                if target["is_super_admin"] and player_id != int(admin["id"]):
                    return json_error("protected_account", 403)
                await conn.execute(
                    "UPDATE players SET telegram_id = $1 WHERE id = $2",
                    telegram_id, player_id,
                )
                await conn.execute(
                    "UPDATE player_sessions SET revoked_at = NOW() WHERE player_id = $1 AND revoked_at IS NULL",
                    player_id,
                )
                await conn.execute(
                    "DELETE FROM telegram_login_requests WHERE telegram_id = $1",
                    telegram_id,
                )
        return web.json_response({"ok": True, "message": "telegram_id_linked"})
    except asyncpg.UniqueViolationError:
        return json_error("telegram_id_exists", 409)


async def admin_houses_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch("SELECT id, name, castle, treasury, food, resources, annual_income FROM houses ORDER BY name")
    houses = []
    for row in rows:
        item = dict(row)
        for field in ("resources", "annual_income"):
            value = item.get(field) or {}
            if isinstance(value, str):
                import json
                try:
                    value = json.loads(value)
                except (TypeError, ValueError):
                    value = {}
            item[field] = value
        houses.append(item)
    return web.json_response({"ok": True, "houses": houses})


async def admin_update_house_economy_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    import json
    try:
        house_id = int(request.match_info["house_id"])
        data = await request.json()
        allowed = {"wood","stone","iron","coins","food","subjects","warhorses","fur","wool","wine","spice","black_iron","salt"}
        cleaned = []
        for field in ("resources", "annual_income"):
            source = data.get(field, {})
            if not isinstance(source, dict):
                return json_error("invalid_economy_data")
            values = {}
            for key, raw in source.items():
                if key not in allowed or isinstance(raw, bool):
                    return json_error("invalid_resource_category")
                amount = int(raw)
                if amount < 0 or amount > 9000000000000:
                    return json_error("invalid_resource_amount")
                values[key] = amount
            cleaned.append(values)
        resources, annual_income = cleaned
    except (ValueError, TypeError):
        return json_error("invalid_economy_data")
    async with request.app["db"].acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE houses
               SET resources = $1::jsonb, annual_income = $2::jsonb,
                   treasury = COALESCE(($1::jsonb->>'coins')::bigint, treasury),
                   food = COALESCE(($1::jsonb->>'food')::bigint, food)
               WHERE id = $3
               RETURNING id, name, treasury, food, resources, annual_income""",
            json.dumps(resources, ensure_ascii=False),
            json.dumps(annual_income, ensure_ascii=False),
            house_id,
        )
    if not row:
        return json_error("house_not_found", 404)
    result = dict(row)
    for field in ("resources", "annual_income"):
        value = result.get(field) or {}
        if isinstance(value, str):
            result[field] = json.loads(value)
    return web.json_response({"ok": True, "house": result})


async def admin_assign_castle_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    try:
        player_id = int(request.match_info["player_id"])
        data = await request.json()
        raw_castle = data.get("castle_name")
        castle_name = str(raw_castle).strip() if raw_castle not in (None, "") else None
    except (ValueError, TypeError):
        return json_error("invalid_castle_assignment")
    if castle_name is not None and len(castle_name) > 150:
        return json_error("invalid_castle_name")
    async with request.app["db"].acquire() as conn:
        if castle_name is not None:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM houses WHERE castle = $1)",
                castle_name,
            )
            if not exists:
                return json_error("castle_not_found", 404)
        row = await conn.fetchrow(
            "UPDATE players SET castle_name = $1 WHERE id = $2 RETURNING id, username, castle_name",
            castle_name, player_id,
        )
    if not row:
        return json_error("player_not_found", 404)
    return web.json_response({"ok": True, "player": dict(row)})


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
            UPDATE players p
            SET house_id = $1,
                castle_name = (SELECT castle FROM houses WHERE id = $1)
            WHERE p.id = $2
            RETURNING p.id, p.username, p.house_id, p.castle_name
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
    try:
        profile_id = int(data.get("profile_id", 0))
    except (TypeError, ValueError):
        return json_error("invalid_profile_id")

    if not raw_id.isdigit():
        return json_error("invalid_telegram_id")
    telegram_id = int(raw_id)
    if telegram_id <= 0 or telegram_id > 9223372036854775807:
        return json_error("invalid_telegram_id")
    if profile_id <= 0:
        return json_error("invalid_profile_id")

    try:
        async with request.app["db"].acquire() as conn:
            async with conn.transaction():
                # Serialize registrations and lock the selected character to prevent double assignment.
                await conn.execute("SELECT pg_advisory_xact_lock(739201847)")
                profile = await conn.fetchrow(
                    "SELECT id, character_name, owner_player_id FROM character_profiles WHERE id = $1 FOR UPDATE",
                    profile_id,
                )
                if not profile:
                    return json_error("profile_not_found", 404)
                if profile["owner_player_id"] is not None:
                    return json_error("profile_already_assigned", 409)
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
                    VALUES ($1, '', $2, 'player', NULL, TRUE, NOW(), FALSE)
                    RETURNING id, username, telegram_id, role, house_id,
                              is_active, is_super_admin
                    """,
                    profile["character_name"], telegram_id,
                )
                await conn.execute(
                    "UPDATE character_profiles SET owner_player_id = $1, updated_at = NOW() WHERE id = $2",
                    player["id"], profile_id,
                )
        return web.json_response({"ok": True, "player": dict(player), "profile_id": profile_id}, status=201)
    except asyncpg.UniqueViolationError:
        return json_error("telegram_id_exists", 409)


async def mail_players_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.id, p.username, p.house_id, h.name AS house_name,
                   COALESCE(
                       ARRAY_AGG(DISTINCT cp.character_name ORDER BY cp.character_name)
                           FILTER (WHERE cp.character_name IS NOT NULL),
                       ARRAY[]::VARCHAR[]
                   ) AS characters
            FROM players p
            LEFT JOIN houses h ON h.id = p.house_id
            LEFT JOIN character_profiles cp
              ON cp.owner_player_id = p.id
              OR LOWER(cp.character_name) = LOWER(p.username)
            WHERE p.is_active = TRUE AND p.id <> $1
            GROUP BY p.id, p.username, p.house_id, h.name
            ORDER BY p.username, p.id
            """,
            player["id"],
        )
    return web.json_response({"ok": True, "players": [dict(row) for row in rows]})



async def market_listings_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch("""
            SELECT l.id, l.item_name, l.quantity, l.unit_price, l.currency,
                   l.note, l.created_at, l.status, l.seller_house_id, l.seller_player_id,
                   h.name AS house_name, p.username AS seller_name
            FROM market_listings l
            JOIN houses h ON h.id = l.seller_house_id
            JOIN players p ON p.id = l.seller_player_id
            WHERE l.status = 'active'
            ORDER BY l.created_at DESC
            LIMIT 200
        """)
    listings = []
    for row in rows:
        item = dict(row)
        item["created_at"] = item["created_at"].isoformat()
        item["quantity"] = int(item["quantity"])
        item["unit_price"] = int(item["unit_price"])
        item["total_price"] = item["quantity"] * item["unit_price"]
        item["is_mine"] = int(item["seller_player_id"]) == int(player["id"])
        listings.append(item)
    return web.json_response({"ok": True, "listings": listings})


async def market_create_listing_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    if not player.get("house_id"):
        return json_error("player_has_no_house", 403)
    try:
        data = await request.json()
        item_name = str(data.get("item_name", "")).strip()
        quantity = int(data.get("quantity", 0))
        unit_price = int(data.get("unit_price", 0))
        note = str(data.get("note", "")).strip()
    except (ValueError, TypeError, Exception):
        return json_error("invalid_listing")
    if item_name not in TRADE_GOODS:
        return json_error("invalid_item_name")
    if quantity < 1 or quantity > 1000000000 or unit_price < 1 or unit_price > 1000000000:
        return json_error("invalid_quantity_or_price")
    if quantity * unit_price > 9000000000000000:
        return json_error("price_overflow")
    if len(note) > 1000:
        return json_error("note_too_long")
    async with request.app["db"].acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO market_listings
                (seller_player_id, seller_house_id, item_name, quantity,
                 unit_price, currency, note, status)
            VALUES ($1, $2, $3, $4, $5, 'سکه', $6, 'active')
            RETURNING id
        """, player["id"], player["house_id"], item_name, quantity, unit_price, note)
    return web.json_response({"ok": True, "listing_id": int(row["id"])})


async def market_cancel_listing_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    try:
        listing_id = int(request.match_info["listing_id"])
    except ValueError:
        return json_error("invalid_listing_id")
    async with request.app["db"].acquire() as conn:
        result = await conn.execute("""
            UPDATE market_listings
            SET status = 'cancelled', updated_at = NOW()
            WHERE id = $1 AND seller_player_id = $2 AND status = 'active'
        """, listing_id, player["id"])
    if result.endswith(" 0"):
        return json_error("listing_not_found_or_not_owned", 404)
    return web.json_response({"ok": True})

async def trade_houses_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch("SELECT id, name FROM houses WHERE id <> COALESCE($1, 0) ORDER BY name", player.get("house_id"))
    return web.json_response({"ok": True, "houses": [dict(r) for r in rows]})


async def trade_contracts_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    if not player.get("house_id"):
        return json_error("player_has_no_house", 403)
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch("""
            SELECT c.*, ph.name AS proposer_house_name, rh.name AS recipient_house_name,
                   pp.username AS proposer_name, rp.username AS recipient_name,
                   (c.proposer_house_id = $1) AS is_proposer_house,
                   (c.recipient_house_id = $1) AS is_recipient_house
            FROM trade_contracts c
            JOIN houses ph ON ph.id = c.proposer_house_id
            JOIN houses rh ON rh.id = c.recipient_house_id
            JOIN players pp ON pp.id = c.proposer_player_id
            LEFT JOIN players rp ON rp.id = c.recipient_player_id
            WHERE c.proposer_house_id = $1 OR c.recipient_house_id = $1
            ORDER BY c.created_at DESC LIMIT 100
        """, player["house_id"])
    contracts = []
    for row in rows:
        item = dict(row)
        item["created_at"] = item["created_at"].isoformat()
        item["responded_at"] = item["responded_at"].isoformat() if item["responded_at"] else None
        for key in ("offered_quantity", "requested_quantity", "penalty_coins"):
            item[key] = int(item[key])
        contracts.append(item)
    return web.json_response({"ok": True, "contracts": contracts})


async def trade_contract_create_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    if not player.get("house_id"):
        return json_error("player_has_no_house", 403)
    try:
        data = await request.json()
        recipient_house_id = int(data.get("recipient_house_id", 0))
        offered_item = str(data.get("offered_item", "")).strip()
        offered_quantity = int(data.get("offered_quantity", 0))
        requested_item = str(data.get("requested_item", "")).strip()
        requested_quantity = int(data.get("requested_quantity", 0))
        duration_years = int(data.get("duration_years", 0))
        penalty_coins = int(data.get("penalty_coins", 0))
    except Exception:
        return json_error("invalid_contract")
    if recipient_house_id <= 0 or recipient_house_id == int(player["house_id"]):
        return json_error("invalid_recipient_house")
    if offered_item not in TRADE_GOODS or requested_item not in TRADE_GOODS:
        return json_error("invalid_contract_item")
    if not (1 <= offered_quantity <= 1000000000 and 1 <= requested_quantity <= 1000000000):
        return json_error("invalid_contract_quantity")
    if not (1 <= duration_years <= 100 and 0 <= penalty_coins <= 1000000000000):
        return json_error("invalid_contract_terms")
    async with request.app["db"].acquire() as conn:
        exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM houses WHERE id = $1)", recipient_house_id)
        if not exists:
            return json_error("recipient_house_not_found", 404)
        row = await conn.fetchrow("""
            INSERT INTO trade_contracts
                (proposer_player_id, proposer_house_id, recipient_house_id,
                 offered_item, offered_quantity, requested_item, requested_quantity,
                 duration_years, penalty_coins)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id
        """, player["id"], player["house_id"], recipient_house_id, offered_item,
             offered_quantity, requested_item, requested_quantity, duration_years, penalty_coins)
    return web.json_response({"ok": True, "contract_id": int(row["id"])})


async def trade_contract_respond_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    if not player.get("house_id"):
        return json_error("player_has_no_house", 403)
    try:
        contract_id = int(request.match_info["contract_id"])
        data = await request.json()
        decision = str(data.get("decision", "")).strip().lower()
    except Exception:
        return json_error("invalid_response")
    if decision not in ("accept", "reject"):
        return json_error("invalid_decision")
    status = "accepted" if decision == "accept" else "rejected"
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                SELECT id, recipient_house_id, status FROM trade_contracts
                WHERE id = $1 FOR UPDATE
            """, contract_id)
            if not row or int(row["recipient_house_id"]) != int(player["house_id"]):
                return json_error("contract_not_found_or_not_for_house", 404)
            if row["status"] != "pending":
                return json_error("contract_already_answered", 409)
            await conn.execute("""
                UPDATE trade_contracts SET status = $1, recipient_player_id = $2,
                    responded_at = NOW() WHERE id = $3
            """, status, player["id"], contract_id)
    return web.json_response({"ok": True, "status": status})


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
                   l.read_at, l.is_anonymous,
                   CASE WHEN $1 = 'inbox' AND l.is_anonymous THEN NULL ELSE p.id END AS other_player_id,
                   CASE WHEN $1 = 'inbox' AND l.is_anonymous THEN 'ناشناس' ELSE p.username END AS other_player
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


async def mail_unread_count_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player["is_active"]:
        return json_error("unauthorized", 401)
    async with request.app["db"].acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM game_letters WHERE recipient_player_id = $1 AND read_at IS NULL",
            player["id"],
        )
    return web.json_response({"ok": True, "unread_count": int(count or 0)})


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
    is_anonymous = data.get("is_anonymous", False) is True
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
                (sender_player_id, recipient_player_id, subject, body, category, is_anonymous, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING id, created_at
            """,
            player["id"], recipient_id, subject, body, category, is_anonymous,
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


async def read_game_clock(conn):
    row = await conn.fetchrow("""
        SELECT game_year, is_running,
               CASE WHEN is_running AND started_at IS NOT NULL
                    THEN elapsed_seconds + GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - started_at))))::BIGINT
                    ELSE elapsed_seconds END AS total_elapsed_seconds
        FROM game_clock WHERE id = 1
    """)
    if not row:
        return None
    total_seconds = int(row["total_elapsed_seconds"] or 0)
    seasons = [("spring", "بهار", "🌱"), ("summer", "تابستان", "☀️"),
               ("autumn", "پاییز", "🍂"), ("winter", "زمستان", "❄️")]
    season_key, season_label, season_icon = seasons[int((total_seconds % 691200) // 172800)]
    game_year = int(row["game_year"]) + (total_seconds // 86400)
    is_peace_period = game_year < 136  # Years 129–135 AC: the first seven game years.
    return {
        "game_year": game_year,
        "season": season_key, "season_label": season_label, "season_icon": season_icon,
        "is_running": bool(row["is_running"]), "total_elapsed_seconds": total_seconds,
        "seconds_until_season": 172800 - (total_seconds % 172800),
        "seconds_until_year": 86400 - (total_seconds % 86400),
        "is_peace_period": is_peace_period,
        "peace_years_remaining": max(0, 136 - game_year),
        "campaigns_allowed": not is_peace_period,
        "peace_ends_at_year": 136,
    }



def _json_object(value):
    if isinstance(value, str):
        import json
        try: value = json.loads(value)
        except (TypeError, ValueError): value = {}
    return value if isinstance(value, dict) else {}


def _level(buildings, name):
    def norm(v):
        value = str(v or "").replace("\u200c", "").replace(" ", "").replace("ي", "ی").replace("ك", "ک")
        if value in ("پرورشاسبجنگی", "پرورشگاهاسبجنگی"):
            return "پرورشگاهاسبجنگی"
        return value
    target = norm(name)
    levels = []
    for key, value in buildings.items():
        if norm(key) == target:
            try:
                levels.append(max(0, min(5, int(value))))
            except (ValueError, TypeError):
                continue
    return max(levels, default=0)


def _house_special_region(house_name):
    name = str(house_name or "").replace("\u200c", "").replace(" ", "")
    regions = {
        "استارک":"north", "کارستارک":"north", "داستین":"north", "آمبر":"north",
        "آرین":"vale", "رویس":"vale", "کوربری":"vale",
        "گریجوی":"iron", "هارلاو":"iron", "گودبروتر":"iron", "بلک‌تاید":"iron", "بلکتاید":"iron",
        "تالی":"river", "فری":"river", "برکن":"river", "بلک‌وود":"river",
        "لنیستر":"west", "کراکهال":"west", "لفورد":"west",
        "تارگرین":"crown", "سیلتیگار":"crown", "ولاریون":"crown", "دارکلین":"crown",
        "بارثیون":"storm", "کارون":"storm", "فل":"storm", "سوان":"storm",
        "تایرل":"reach", "ردواین":"reach", "های‌تاور":"reach", "تارلی":"reach",
        "مارتل":"dorne", "مارتل‌ها":"dorne", "دین":"dorne", "یرونوود":"dorne", "آلیرین":"dorne", "فاولر":"dorne",
    }
    return regions.get(name)


def _settle_house_build_queue(state, now_ms):
    queue = state.get("queue")
    if not isinstance(queue, list) or not queue:
        return False
    buildings = state.setdefault("buildings", {})
    remaining = []
    changed = False
    for job in queue:
        if not isinstance(job, dict):
            changed = True
            continue
        try:
            started = float(job.get("started") or 0)
            duration = float(job.get("duration") or 0)
        except (TypeError, ValueError):
            remaining.append(job)
            continue
        if started <= 0 or duration <= 0 or now_ms < started + duration:
            remaining.append(job)
            continue
        name = str(job.get("name") or "")
        current = _level(buildings, name)
        try:
            target = int(job.get("targetLevel") or (current + 1))
        except (TypeError, ValueError):
            target = current + 1
        if name and current < 5 and current < target <= 5:
            buildings[name] = target
        changed = True
    if changed:
        state["queue"] = remaining
    return changed


def _apply_house_annual_income(state, elapsed, special_region=None):
    resources = state.setdefault("resources", {})
    special = resources.setdefault("specialGoods", {})
    buildings = state.setdefault("buildings", {})
    standard = [
        ("ماهیگیری", "food", 8, 1), ("مزرعه", "food", 12, 1),
        ("چوب‌بری", "wood", 14, 2), ("معدن سنگ", "stone", 8, 3),
        ("معدن آهن", "iron", 5, 4), ("بازار", "coins", 500, 2),
        ("شهر", "subjects", 3, 5),
    ]
    totals = {}
    upkeep = 0
    regional_bonus = {
        "west": {"coins": 1.5},
        "reach": {"food": 1.5},
        "river": {"food": 1.5},
        "storm": {"wood": 1.5},
        "vale": {"stone": 1.5},
        "iron": {"iron": 1.5},
        "north": {"wood": 1.5},
        # Dorne's fishery is its signature food source.
        "dorne": {"fishery": 2.0},
    }.get(special_region, {})
    for name, key, base, food_cost in standard:
        level = _level(buildings, name)
        multiplier = regional_bonus.get("fishery", 1.0) if name == "ماهیگیری" else regional_bonus.get(key, 1.0)
        totals[key] = totals.get(key, 0) + int(level * base * multiplier) * elapsed
        upkeep += level * food_cost * elapsed
    special_buildings = [
        ("north", "شکارگاه", "fur", [60,105,165,240,330]),
        ("vale", "دامداری پشمی", "wool", [90,165,255,375,525]),
        ("reach", "تاکستان", "wine", [75,135,210,300,420]),
        ("storm", "پرورشگاه اسب جنگی", "warhorses", [3,6,9,15,21]),
        ("dorne", "باغ ادویه", "spice", [60,105,165,240,345]),
        ("crown", "نمک‌زار", "salt", [90,165,255,375,510]),
        ("iron", "معدن آهن سیاه", "blackIron", [45,90,150,225,315]),
    ]
    for region, name, key, yields in special_buildings:
        if special_region != region:
            continue
        level = _level(buildings, name)
        if level:
            amount = yields[level-1] * elapsed
            if key == "warhorses":
                resources["warhorses"] = int(resources.get("warhorses", 0) or 0) + amount
            else:
                special[key] = int(special.get(key, 0) or 0) + amount
    for key, amount in totals.items():
        resources[key] = int(resources.get(key, 0) or 0) + amount
    resources["food"] = max(0, int(resources.get("food", 0) or 0) - upkeep)
    state["resources"] = resources
    state["buildings"] = buildings
    return state


def _canonical_house_resources(house_resources, game_resources):
    house_resources = house_resources if isinstance(house_resources, dict) else {}
    game_resources = game_resources if isinstance(game_resources, dict) else {}
    result = {
        "wood": 0, "stone": 0, "iron": 0, "coins": 0,
        "food": 0, "subjects": 0, "warhorses": 0,
    }
    result.update(game_resources)
    for key in ("wood", "stone", "iron", "coins", "food", "subjects", "warhorses"):
        if key in house_resources:
            result[key] = house_resources[key]
    # Older versions stored warhorse-building output under specialGoods.
    # Fold that legacy stock into the canonical warehouse field.
    legacy_special = game_resources.get("specialGoods") or {}
    try:
        legacy_warhorses = max(0, int(legacy_special.get("warhorses", 0) or 0))
        result["warhorses"] = int(result.get("warhorses", 0) or 0) + legacy_warhorses
    except (TypeError, ValueError):
        pass
    special = {
        "fur": 0, "wool": 0, "wine": 0, "spice": 0, "salt": 0, "blackIron": 0,
    }
    special.update({k: v for k, v in legacy_special.items() if k != "warhorses"})
    for source, target in (("fur", "fur"), ("wool", "wool"), ("wine", "wine"),
                           ("spice", "spice"), ("salt", "salt"),
                           ("black_iron", "blackIron"), ("blackIron", "blackIron")):
        if source in house_resources:
            special[target] = house_resources[source]
    result["specialGoods"] = special
    return result


async def _settle_all_house_annual_income(conn, game_year):
    import json
    rows = await conn.fetch(
        "SELECT id, name, game_state, resources FROM houses ORDER BY id FOR UPDATE"
    )
    settled = 0
    for row in rows:
        state = _json_object(row["game_state"])
        house_resources = _json_object(row["resources"])
        state["resources"] = _canonical_house_resources(house_resources, state.get("resources"))
        last_year = int(state.get("_lastIncomeYear", 129) or 129)
        elapsed = max(0, int(game_year) - last_year)
        if not elapsed:
            continue
        state = _apply_house_annual_income(
            state, elapsed, _house_special_region(row["name"])
        )
        state["_lastIncomeYear"] = int(game_year)
        resources = state.get("resources") or {}
        special = resources.get("specialGoods") or {}
        for key in ("wood", "stone", "iron", "coins", "food", "subjects", "warhorses"):
            if key in resources:
                house_resources[key] = resources[key]
        for key, source in (("fur", "fur"), ("wool", "wool"), ("wine", "wine"),
                            ("spice", "spice"), ("salt", "salt"), ("black_iron", "blackIron")):
            if source in special:
                house_resources[key] = special[source]
        await conn.execute(
            """
            UPDATE houses
            SET game_state=$1::jsonb, resources=$2::jsonb, game_state_updated_at=NOW()
            WHERE id=$3
            """,
            json.dumps(state, ensure_ascii=False),
            json.dumps(house_resources, ensure_ascii=False),
            row["id"],
        )
        settled += 1
    return settled


async def my_house_state_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    if not player.get("house_id"):
        return json_error("house_not_assigned", 409)
    import json
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT game_state, resources, game_state_updated_at FROM houses WHERE id=$1 FOR UPDATE", player["house_id"])
            if not row:
                return json_error("house_not_found", 404)
            state = _json_object(row["game_state"])
            house_resources = _json_object(row["resources"])
            state["resources"] = _canonical_house_resources(house_resources, state.get("resources"))
            updated_at = row["game_state_updated_at"]
            if not updated_at:
                updated_at = await conn.fetchval(
                    "UPDATE houses SET game_state_updated_at=NOW() WHERE id=$1 RETURNING game_state_updated_at",
                    player["house_id"],
                )
            clock = await read_game_clock(conn)
            changed = False
            if clock:
                if clock.get("is_running"):
                    import time
                    changed = _settle_house_build_queue(state, time.time() * 1000) or changed
                year = int(clock["game_year"])
                last_year = int(state.get("_lastIncomeYear", 129) or 129)
                elapsed = max(0, year - last_year)
                if elapsed:
                    state = _apply_house_annual_income(
                        state, elapsed, _house_special_region(player.get("house_name"))
                    )
                    state["_lastIncomeYear"] = year
                    changed = True
            if changed:
                resources = state.get("resources") or {}
                special = resources.get("specialGoods") or {}
                for key in ("wood", "stone", "iron", "coins", "food", "subjects", "warhorses"):
                    if key in resources:
                        house_resources[key] = resources[key]
                for key, source in (("fur", "fur"), ("wool", "wool"), ("wine", "wine"),
                                    ("spice", "spice"), ("salt", "salt"), ("black_iron", "blackIron")):
                    if source in special:
                        house_resources[key] = special[source]
                await conn.execute(
                    "UPDATE houses SET game_state=$1::jsonb, resources=$2::jsonb, game_state_updated_at=NOW() WHERE id=$3",
                    json.dumps(state, ensure_ascii=False), json.dumps(house_resources, ensure_ascii=False),
                    player["house_id"],
                )
                updated_at = await conn.fetchval("SELECT game_state_updated_at FROM houses WHERE id=$1", player["house_id"])
    return web.json_response({"ok": True, "state": state, "updated_at": updated_at.isoformat() if updated_at else None, "game_year": clock["game_year"] if clock else None})


async def my_house_state_update_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    if not player.get("house_id"):
        return json_error("house_not_assigned", 409)
    import json
    try:
        data = await request.json()
        if not isinstance(data, dict): return json_error("invalid_state")
        incoming = {}
        for key in ("resources", "buildings", "queue"):
            value = data.get(key)
            if not isinstance(value, (dict, list)): return json_error("invalid_state")
            incoming[key] = value
        for key in ("wood","stone","iron","coins","food","subjects","warhorses"):
            if key in incoming["resources"]:
                raw = incoming["resources"][key]
                if isinstance(raw, bool) or int(raw) < 0: return json_error("invalid_resource_amount")
                incoming["resources"][key] = int(raw)
        if len(incoming["queue"]) > 2: return json_error("invalid_build_queue")
    except (ValueError, TypeError):
        return json_error("invalid_state")
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT game_state, game_state_updated_at FROM houses WHERE id=$1 FOR UPDATE", player["house_id"])
            if not row: return json_error("house_not_found", 404)
            expected_updated_at = data.get("expected_updated_at")
            current_updated_at = row["game_state_updated_at"]
            if not current_updated_at or not expected_updated_at or expected_updated_at != current_updated_at.isoformat():
                return json_error("stale_house_state", 409)
            current = _json_object(row["game_state"])
            current.update(incoming)
            house_resources = _json_object(await conn.fetchval(
                "SELECT resources FROM houses WHERE id=$1", player["house_id"]
            ))
            resources = incoming["resources"]
            for key in ("wood", "stone", "iron", "coins", "food", "subjects", "warhorses"):
                if key in resources:
                    house_resources[key] = resources[key]
            special = resources.get("specialGoods") if isinstance(resources.get("specialGoods"), dict) else {}
            for source, target in (("fur", "fur"), ("wool", "wool"), ("wine", "wine"),
                                   ("spice", "spice"), ("salt", "salt"), ("blackIron", "black_iron")):
                if source in special:
                    house_resources[target] = special[source]
            await conn.execute(
                "UPDATE houses SET game_state=$1::jsonb, resources=$2::jsonb, game_state_updated_at=NOW() WHERE id=$3",
                json.dumps(current, ensure_ascii=False), json.dumps(house_resources, ensure_ascii=False),
                player["house_id"],
            )
            updated_at = await conn.fetchval("SELECT game_state_updated_at FROM houses WHERE id=$1", player["house_id"])
    return web.json_response({"ok": True, "updated_at": updated_at.isoformat() if updated_at else None})


async def game_clock_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            clock = await read_game_clock(conn)
            if clock:
                await _settle_all_house_annual_income(conn, int(clock["game_year"]))
    if not clock:
        return json_error("game_clock_unavailable", 503)
    return web.json_response({"ok": True, **clock})


async def admin_game_clock_start_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT is_running FROM game_clock WHERE id = 1 FOR UPDATE")
            if not row:
                return json_error("game_clock_unavailable", 503)
            if not row["is_running"]:
                await conn.execute("UPDATE game_clock SET is_running = TRUE, started_at = NOW() WHERE id = 1")
            clock = await read_game_clock(conn)
    return web.json_response({"ok": True, **clock})


async def admin_game_clock_pause_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT is_running, started_at FROM game_clock WHERE id = 1 FOR UPDATE")
            if not row:
                return json_error("game_clock_unavailable", 503)
            if row["is_running"] and row["started_at"]:
                await conn.execute("""
                    UPDATE game_clock
                    SET elapsed_seconds = elapsed_seconds + GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - started_at))))::BIGINT,
                        is_running = FALSE, started_at = NULL
                    WHERE id = 1
                """)
            clock = await read_game_clock(conn)
    return web.json_response({"ok": True, **clock})



async def game_state_control_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    async with request.app["db"].acquire() as conn:
        row = await conn.fetchrow("""
            SELECT c.reset_version, c.economy_reset_version, g.is_running
            FROM game_state_control c
            CROSS JOIN game_clock g
            WHERE c.id = 1 AND g.id = 1
        """)
    if not row:
        return json_error("game_state_control_unavailable", 503)
    return web.json_response({
        "ok": True,
        "reset_version": int(row["reset_version"]),
        "economy_reset_version": int(row["economy_reset_version"]),
        "is_running": bool(row["is_running"]),
    })


async def admin_reset_game_state_handler(request):
    player, error = await require_super_admin(request)
    if error:
        return error
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT reset_version FROM game_state_control WHERE id = 1 FOR UPDATE"
            )
            if not row:
                return json_error("game_state_control_unavailable", 503)
            next_version = int(row["reset_version"]) + 1
            await conn.execute(
                "UPDATE game_state_control SET reset_version = $1, updated_at = NOW() WHERE id = 1",
                next_version,
            )
            await conn.execute("UPDATE houses SET treasury = 0, food = 0")
            await conn.execute("UPDATE houses SET game_state='{}'::jsonb, game_state_updated_at=NULL")
            await conn.execute("""
                UPDATE game_clock
                SET game_year = 129, season = 'spring', is_running = FALSE,
                    started_at = NULL, elapsed_seconds = 0,
                    last_year_update = NULL, last_season_update = NULL
                WHERE id = 1
            """)
    return web.json_response({
        "ok": True,
        "reset_version": next_version,
        "game_year": 129,
        "season": "spring",
        "is_running": False,
        "message": "game_state_reset_to_defaults",
    })


async def admin_reset_economy_handler(request):
    player, error = await require_super_admin(request)
    if error:
        return error
    async with request.app["db"].acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT economy_reset_version FROM game_state_control WHERE id = 1 FOR UPDATE"
            )
            if not row:
                return json_error("game_state_control_unavailable", 503)
            next_version = int(row["economy_reset_version"]) + 1
            clock = await read_game_clock(conn)
            current_year = int((clock or {}).get("game_year") or 129)
            base_resources = {
                "wood": 1240, "stone": 680, "iron": 45, "coins": 910,
                "food": 120, "subjects": 38, "warhorses": 0,
            }
            regional_resource = {
                "west": ("coins", 1.5),
                "reach": ("food", 1.5),
                "river": ("food", 1.5),
                "storm": ("wood", 1.5),
                "vale": ("stone", 1.5),
                "iron": ("iron", 1.5),
                "north": ("wood", 1.5),
                "dorne": ("food", 1.5),
            }
            import json
            await conn.execute(
                "UPDATE game_state_control SET economy_reset_version = $1, updated_at = NOW() WHERE id = 1",
                next_version,
            )
            houses = await conn.fetch("SELECT id, name FROM houses ORDER BY id FOR UPDATE")
            for house in houses:
                initial = dict(base_resources)
                region = _house_special_region(house["name"])
                bonus = regional_resource.get(region)
                if bonus:
                    key, factor = bonus
                    initial[key] = int(initial[key] * factor)
                default_resources = {
                    **initial,
                    "specialGoods": {
                        "fur": 0, "wool": 0, "wine": 0, "spice": 0,
                        "salt": 0, "blackIron": 0,
                    },
                }
                house_resources = {
                    **initial,
                    "fur": 0, "wool": 0, "wine": 0, "spice": 0,
                    "salt": 0, "black_iron": 0,
                }
                default_state = {
                    "resources": default_resources,
                    "buildings": {"مزرعه": 1, "چوب‌بری": 1, "معدن سنگ": 1, "شهر": 1},
                    "queue": [],
                    "_lastIncomeYear": current_year,
                }
                await conn.execute(
                    """
                    UPDATE houses
                    SET treasury = $1,
                        food = $2,
                        resources = $3::jsonb,
                        game_state = $4::jsonb,
                        game_state_updated_at = NOW()
                    WHERE id = $5
                    """,
                    initial["coins"], initial["food"],
                    json.dumps(house_resources, ensure_ascii=False),
                    json.dumps(default_state, ensure_ascii=False),
                    house["id"],
                )
    return web.json_response({
        "ok": True,
        "economy_reset_version": next_version,
        "game_year": current_year,
        "houses_reset": True,
        "message": "player_resources_and_buildings_reset",
    })


async def profiles_list_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    is_admin = bool(player.get("is_super_admin") and player.get("role") == "admin")
    async with request.app["db"].acquire() as conn:
        if is_admin:
            rows = await conn.fetch("""
                SELECT id, character_name, title, location, house, gender, owner_player_id
                FROM character_profiles ORDER BY character_name
            """)
        else:
            # The personal profile section lists only characters assigned to this player.
            # Public biographies remain available through /api/profiles/public (court pages).
            rows = await conn.fetch("""
                SELECT id, character_name, title, location, house, gender
                FROM character_profiles
                WHERE owner_player_id = $1
                ORDER BY character_name
            """, player["id"])
        profiles = [dict(row) for row in rows]
        players = []
        if is_admin:
            players = [dict(r) for r in await conn.fetch(
                "SELECT id, username FROM players ORDER BY username"
            )]
    return web.json_response({"ok": True, "profiles": profiles, "is_admin": is_admin, "players": players})


async def public_profiles_list_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    is_admin = bool(player.get("is_super_admin") and player.get("role") == "admin")
    async with request.app["db"].acquire() as conn:
        if is_admin:
            # Admin's new-player form must offer the full roster, including
            # characters that have not been assigned to any player yet.
            rows = await conn.fetch("""
                SELECT id, character_name, title, location, house
                FROM character_profiles
                ORDER BY character_name
            """)
        else:
            rows = await conn.fetch("""
                SELECT id, character_name, title, location, house
                FROM character_profiles
                WHERE owner_player_id IS NOT NULL
                ORDER BY character_name
            """)
    return web.json_response({"ok": True, "profiles": [dict(row) for row in rows]})


async def profile_detail_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    try:
        profile_id = int(request.match_info["profile_id"])
    except (ValueError, TypeError):
        return json_error("invalid_profile_id")
    is_admin = bool(player.get("is_super_admin") and player.get("role") == "admin")
    async with request.app["db"].acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, character_name, biography, age, health, title, location,
                   spouse, gender, children, dragon, house, owner_player_id,
                   warfare, intelligence, diplomacy, management, faith
            FROM character_profiles WHERE id = $1
        """, profile_id)
    if not row:
        return json_error("profile_not_found", 404)
    data = dict(row)
    owner_id = data.pop("owner_player_id")
    can_view_skills = is_admin or owner_id == player["id"]
    skills = None
    if can_view_skills:
        skills = {key: data.pop(key) for key in ("warfare", "intelligence", "diplomacy", "management", "faith")}
    else:
        for key in ("warfare", "intelligence", "diplomacy", "management", "faith"):
            data.pop(key, None)
    data["skills"] = skills
    data["is_owner"] = owner_id == player["id"]
    if is_admin:
        data["owner_player_id"] = owner_id
    return web.json_response({"ok": True, "profile": data})


async def admin_update_profile_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    try:
        profile_id = int(request.match_info["profile_id"])
        data = await request.json()
    except (ValueError, TypeError):
        return json_error("invalid_request")
    public_fields = ("biography", "age", "health", "title", "location", "spouse", "children", "dragon", "house")
    values = {}
    for key in public_fields:
        value = data.get(key)
        if value is not None:
            value = str(value).strip()
            if len(value) > (3000 if key == "biography" else 500):
                return json_error("field_too_long")
        values[key] = value or None
    gender = str(data.get("gender") or "unknown").strip().lower()
    if gender not in ("male", "female", "unknown"):
        return json_error("invalid_gender")
    owner_raw = data.get("owner_player_id")
    try:
        owner_id = int(owner_raw) if owner_raw not in (None, "") else None
    except (ValueError, TypeError):
        return json_error("invalid_owner")
    skill_data = data.get("skills") or {}
    skill_values = []
    for key in ("warfare", "intelligence", "diplomacy", "management", "faith"):
        try:
            value = int(skill_data[key])
        except (KeyError, ValueError, TypeError):
            return json_error("invalid_skill")
        if value < 0 or value > 100:
            return json_error("invalid_skill")
        skill_values.append(value)
    async with request.app["db"].acquire() as conn:
        if owner_id is not None and not await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM players WHERE id = $1 AND is_active = TRUE)", owner_id
        ):
            return json_error("owner_not_found", 404)
        updated = await conn.fetchrow("""
            UPDATE character_profiles SET
                biography=$1, age=$2, health=$3, title=$4, location=$5,
                spouse=$6, children=$7, dragon=$8, house=$9, owner_player_id=$10,
                warfare=$11, intelligence=$12, diplomacy=$13, management=$14, faith=$15,
                gender=$16, updated_at=NOW()
            WHERE id=$17 RETURNING id, character_name, gender
        """, *(values[k] for k in public_fields), owner_id, *skill_values, gender, profile_id)
    if not updated:
        return json_error("profile_not_found", 404)
    return web.json_response({"ok": True, "profile": dict(updated)})

async def admin_assign_profile_owner_handler(request):
    admin, error = await require_super_admin(request)
    if error:
        return error
    try:
        profile_id = int(request.match_info["profile_id"])
        data = await request.json()
        owner_raw = data.get("owner_player_id")
        owner_id = int(owner_raw) if owner_raw not in (None, "") else None
    except (ValueError, TypeError):
        return json_error("invalid_request")
    async with request.app["db"].acquire() as conn:
        if owner_id is not None and not await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM players WHERE id = $1 AND is_active = TRUE)", owner_id
        ):
            return json_error("owner_not_found", 404)
        updated = await conn.fetchrow("""
            UPDATE character_profiles
            SET owner_player_id = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING id, character_name, owner_player_id
        """, owner_id, profile_id)
    if not updated:
        return json_error("profile_not_found", 404)
    return web.json_response({"ok": True, "profile": dict(updated)})


async def index_handler(request):
    # Always revalidate the game shell so embedded browsers do not keep an old menu/pages bundle.
    return web.FileResponse(
        WEBAPP_FILE,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


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
        await conn.execute("ALTER TABLE houses ADD COLUMN IF NOT EXISTS resources JSONB NOT NULL DEFAULT '{}'::jsonb")
        await conn.execute("ALTER TABLE houses ADD COLUMN IF NOT EXISTS annual_income JSONB NOT NULL DEFAULT '{}'::jsonb")
        await conn.execute("ALTER TABLE houses ADD COLUMN IF NOT EXISTS game_state JSONB NOT NULL DEFAULT '{}'::jsonb")
        await conn.execute("ALTER TABLE houses ADD COLUMN IF NOT EXISTS game_state_updated_at TIMESTAMPTZ")
        # Bootstrap the player tables on a brand-new database before any queries use them.
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id BIGSERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash TEXT NOT NULL DEFAULT '',
                telegram_id BIGINT UNIQUE,
                role VARCHAR(30) NOT NULL DEFAULT 'player',
                house_id BIGINT REFERENCES houses(id),
                castle_name VARCHAR(150),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_super_admin BOOLEAN NOT NULL DEFAULT FALSE,
                telegram_auth_date BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CHECK (role IN ('admin', 'player', 'house_leader', 'treasurer'))
            )
        """)
        await conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS castle_name VARCHAR(150)")
        await conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN NOT NULL DEFAULT FALSE")
        await conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS telegram_auth_date BIGINT")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS player_sessions (
                id BIGSERIAL PRIMARY KEY,
                player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                session_token_hash TEXT NOT NULL UNIQUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL,
                revoked_at TIMESTAMPTZ
            )
        """)
        await conn.execute("ALTER TABLE player_sessions ADD COLUMN IF NOT EXISTS ip_address VARCHAR(64)")
        await conn.execute("ALTER TABLE player_sessions ADD COLUMN IF NOT EXISTS user_agent TEXT")
        await conn.execute("ALTER TABLE player_sessions ADD COLUMN IF NOT EXISTS install_id VARCHAR(80)")
        await conn.execute("CREATE INDEX IF NOT EXISTS player_sessions_install_created_idx ON player_sessions (install_id, created_at DESC)")
        await conn.execute("CREATE INDEX IF NOT EXISTS player_sessions_player_idx ON player_sessions (player_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS player_sessions_ip_created_idx ON player_sessions (ip_address, created_at DESC)")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS desktop_login_requests (
                code VARCHAR(80) PRIMARY KEY,
                expires_at TIMESTAMPTZ NOT NULL,
                telegram_id BIGINT,
                player_id BIGINT REFERENCES players(id) ON DELETE CASCADE,
                session_token TEXT,
                approved_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS desktop_login_requests_expiry_idx ON desktop_login_requests (expires_at)")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS telegram_login_requests (
                telegram_id BIGINT PRIMARY KEY,
                telegram_username VARCHAR(64) NOT NULL DEFAULT '',
                first_name VARCHAR(128) NOT NULL DEFAULT '',
                last_name VARCHAR(128) NOT NULL DEFAULT '',
                first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                attempt_count INTEGER NOT NULL DEFAULT 1
            )
        """)
        await conn.execute(
            "DELETE FROM telegram_login_requests WHERE last_seen_at < NOW() - INTERVAL '30 days'"
        )

        # Create player rows for known court members who do not yet have an account.
        # If a display name is already taken by another account, keep it unique by
        # suffixing the Telegram ID; never reassign an existing player's Telegram ID.
        for telegram_id, character_name in COURT_PLAYER_ACCOUNTS:
            await conn.execute(
                """
                INSERT INTO players
                    (username, password_hash, telegram_id, role, is_active, is_super_admin)
                SELECT
                    CASE
                        WHEN EXISTS (
                            SELECT 1 FROM players
                            WHERE LOWER(username) = LOWER($2)
                        )
                        THEN LEFT($2, 35) || '_' || $1::text
                        ELSE $2
                    END,
                    '', $1::bigint, 'player', TRUE, FALSE
                WHERE NOT EXISTS (
                    SELECT 1 FROM players WHERE telegram_id = $1::bigint
                )
                ON CONFLICT DO NOTHING
                """,
                str(telegram_id), character_name,
            )

        # Keep the existing Karhold member's display name in sync.
        await conn.execute(
            "UPDATE players SET username = $1 WHERE telegram_id = $2::bigint",
            "Assis Karstark", 8772075836,
        )
        await conn.execute(
            "UPDATE players SET username = $1 WHERE telegram_id = $2::bigint",
            "Roderick Dustin", 6008315341,
        )
        await conn.execute(
            "UPDATE players SET username = $1 WHERE telegram_id = $2::bigint",
            "Karent Crakehall", 7066209583,
        )
        for display_name, member_id in (
            ("Jason Lannister", 7355922500),
            ("Tyland Lannister", 7865635509),
            ("Loren Lannister", 7379737762),
            ("Johanna Lannister", 1606528421),
        ):
            await conn.execute(
                "UPDATE players SET username = $1 WHERE telegram_id = $2::bigint",
                display_name, member_id,
            )

        # Provision the explicitly configured owner account as super-admin.
        super_admin_telegram_id = os.getenv("SUPER_ADMIN_TELEGRAM_ID", "").strip()
        if super_admin_telegram_id.isdigit() and int(super_admin_telegram_id) > 0:
            await conn.execute(
                """
                INSERT INTO players (username, telegram_id, role, is_active, is_super_admin)
                VALUES ($1, $2, 'admin', TRUE, TRUE)
                ON CONFLICT (telegram_id) DO UPDATE
                SET role = 'admin', is_active = TRUE, is_super_admin = TRUE
                """,
                f"superadmin_{super_admin_telegram_id}", int(super_admin_telegram_id),
            )

        for house_name, castle_name in HOUSE_SEEDS:
            await conn.execute(
                """
                INSERT INTO houses (name, castle)
                VALUES ($1, $2)
                ON CONFLICT (name) DO NOTHING
                """,
                house_name, castle_name,
            )
        # Give the flagged super-admin account a default house. This uses the
        # database role flag as the source of truth rather than assuming its
        # players.id is a particular value. Existing house choices are preserved.
        await conn.execute(
            """
            UPDATE players
            SET house_id = (SELECT id FROM houses WHERE name = 'تارگرین')
            WHERE is_super_admin = TRUE AND role = 'admin' AND house_id IS NULL
            """
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
            CREATE TABLE IF NOT EXISTS app_migrations (
                migration_key VARCHAR(150) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        needs_castle_backfill = not await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM app_migrations WHERE migration_key = 'castle-house-defaults-v1')"
        )
        if needs_castle_backfill:
            await conn.execute("""
                UPDATE players p
                SET castle_name = h.castle
                FROM houses h
                WHERE p.house_id = h.id
            """)
            await conn.execute(
                "INSERT INTO app_migrations (migration_key) VALUES ('castle-house-defaults-v1') ON CONFLICT DO NOTHING"
            )
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS character_profiles (
                id BIGSERIAL PRIMARY KEY,
                character_name VARCHAR(180) NOT NULL UNIQUE,
                biography TEXT,
                age VARCHAR(80),
                health VARCHAR(200),
                title VARCHAR(300),
                location VARCHAR(200),
                spouse VARCHAR(300),
                gender VARCHAR(10) NOT NULL DEFAULT 'unknown' CHECK (gender IN ('male','female','unknown')),
                children TEXT,
                dragon VARCHAR(180),
                house VARCHAR(180),
                owner_player_id BIGINT REFERENCES players(id) ON DELETE SET NULL,
                warfare INTEGER NOT NULL DEFAULT 50 CHECK (warfare BETWEEN 0 AND 100),
                intelligence INTEGER NOT NULL DEFAULT 50 CHECK (intelligence BETWEEN 0 AND 100),
                diplomacy INTEGER NOT NULL DEFAULT 50 CHECK (diplomacy BETWEEN 0 AND 100),
                management INTEGER NOT NULL DEFAULT 50 CHECK (management BETWEEN 0 AND 100),
                faith INTEGER NOT NULL DEFAULT 50 CHECK (faith BETWEEN 0 AND 100),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("ALTER TABLE character_profiles ADD COLUMN IF NOT EXISTS gender VARCHAR(10) NOT NULL DEFAULT 'unknown'")
        # Canonical gender tags for the named characters in the current roster.
        await conn.execute("""
            UPDATE character_profiles SET gender='female', updated_at=NOW()
            WHERE lower(character_name) = ANY($1::text[])
        """, [
            'helaena targaryen','alicent hightower','rhaenyra targaryen',
            'rhaenys targaryen','baela targaryen','rhaena targaryen',
            'mysaria','laena velaryon','jeyne arryn','alys rivers',
            'sabitha frey','black aly blackwood','netties',
            'florence fossoway','elinda massey','lady sam',
            'marilda of hull','aemma arryn','ysilla royce',
            'cassella vaith','nymeria sand','tyene sand',
            'tansy tully','sara snow','alys karstark','johanna lannister',
            'jancia fossoway','cassandra baratheon','aliandra martell',
            'coryanne martell','delonne allyrion'
        ])
        await conn.execute("""
            UPDATE character_profiles SET gender='male', updated_at=NOW()
            WHERE gender='unknown' AND lower(character_name) = ANY($1::text[])
        """, [
            'aegon ii targaryen','aemond targaryen','daeron targaryen',
            'alf white','ulf white','daemon targaryen','jacaerys velaryon',
            'hugh hammer','corlys velaryon','adam velaryon','addam velaryon',
            'alyn velaryon','bartimos celtigar','lord reynald darklyn',
            'criston cole','arryk cargyll','erryk cargyll','ser luthor largent',
            'lorent marbrand','willam royce','steffon darklyn',
            'otto hightower','gwayne hightower','orwyle','tyland lannister',
            'jasper wylde','borros baratheon','cregan stark','jacaerys velaryon',
            'robert arryn','gerold royce','harrold westerling',
            'hugh of the vale','oscar tully','grover tully','edmure tully',
            'elmo tully','benjicot blackwood','samwell blackwood',
            'lorent marbrand','garmund hightower','hobert hightower',
            'lord beesbury','lyman beesbury','jason lannister',
            'tyland lannister','addam of hull','qarlo',
            'ormund hightower','jon roxton','gwayne hightower',
            'kermit tully','amos bracken','forrest frey','cregan stark',
            'rickon stark','benjen stark','harmond umber','roderick dustin',
            'loreon lannister','clarrent crakehall','humphrey lefford',
            'lyonel tyrell','loras tyrell','leo tyrell','alan tarly',
            'garth redwyne','royce baratheon','royce caron','byron swann',
            'willis fell','arnold arryn','joffrey arryn','yorbert royce',
            'leowyn corbray','qoren martell','anders yronwood',
            'franklyn fowler','edric dayne','dalton greyjoy','veron greyjoy',
            'harras harlaw','lorren blacktyde','gorold goodbrother'
        ])
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS marriage_proposals (
                id BIGSERIAL PRIMARY KEY,
                groom_player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                bride_player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                groom_profile_id BIGINT NOT NULL REFERENCES character_profiles(id),
                bride_profile_id BIGINT NOT NULL REFERENCES character_profiles(id),
                status VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','accepted','rejected','cancelled')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                responded_at TIMESTAMPTZ
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS marriage_proposals_inbox_idx ON marriage_proposals (bride_player_id,status,created_at DESC)")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS marriages (
                id BIGSERIAL PRIMARY KEY,
                groom_player_id BIGINT NOT NULL REFERENCES players(id),
                bride_player_id BIGINT NOT NULL REFERENCES players(id),
                groom_profile_id BIGINT NOT NULL UNIQUE REFERENCES character_profiles(id),
                bride_profile_id BIGINT NOT NULL UNIQUE REFERENCES character_profiles(id),
                ceremony_level VARCHAR(20),
                ceremony_at TIMESTAMPTZ,
                satisfaction_bonus INTEGER NOT NULL DEFAULT 0,
                satisfaction_expires_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CHECK (ceremony_level IS NULL OR ceremony_level IN ('ordinary','noble','royal'))
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS wedding_invitations (
                id BIGSERIAL PRIMARY KEY,
                marriage_id BIGINT NOT NULL REFERENCES marriages(id) ON DELETE CASCADE,
                invited_player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                response VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (response IN ('pending','attending','declined')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (marriage_id, invited_player_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS wedding_gifts (
                id BIGSERIAL PRIMARY KEY,
                invitation_id BIGINT NOT NULL REFERENCES wedding_invitations(id) ON DELETE CASCADE,
                sender_player_id BIGINT NOT NULL REFERENCES players(id),
                item_name VARCHAR(100) NOT NULL,
                quantity BIGINT NOT NULL CHECK (quantity > 0),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            INSERT INTO character_profiles
                (character_name, title, dragon, house, location, warfare, intelligence, diplomacy, management, faith)
            VALUES
                ('Aegon II Targaryen', 'پادشاه وستروس', 'Sunfyre', 'تارگرین', 'بارانداز پادشاه', 65, 58, 55, 62, 50),
                ('Aemond Targaryen', 'شاهزاده تارگرین', 'Vhagar', 'تارگرین', 'بارانداز پادشاه', 92, 76, 58, 68, 45),
                ('Helaena Targaryen', 'ملکه', 'Dreamfyre', 'تارگرین', 'بارانداز پادشاه', 25, 80, 60, 50, 65),
                ('Daeron Targaryen', 'شاهزاده تارگرین', 'Tessarion', 'تارگرین', 'آب‌دشت', 75, 70, 65, 60, 55),
                ('Alicent Hightower', 'ملکه مادر', NULL, 'های‌تاور', 'بارانداز پادشاه', 25, 85, 90, 80, 85),
                ('Alf White', 'اژدهاسوار', 'Silverwing', NULL, NULL, 70, 60, 50, 45, 40),
                ('Rhaenyra Targaryen', 'مدعی تاج‌وتخت', 'Syrax', 'تارگرین', 'دراگون‌استون', 55, 80, 88, 75, 60),
                ('Daemon Targaryen', 'شاهزاده تارگرین', 'Caraxes', 'تارگرین', 'دراگون‌استون', 95, 78, 60, 65, 30),
                ('Jacaerys Velaryon', 'شاهزاده', 'Vermax', 'ولاریون', 'دراگون‌استون', 72, 82, 85, 70, 55),
                ('Rhaenys Targaryen', 'شاهزاده‌خانم', 'Meleys', 'تارگرین', 'دراگون‌استون', 80, 85, 82, 78, 50),
                ('Baela Targaryen', 'شاهزاده‌خانم', 'Moondancer', 'تارگرین', 'دراگون‌استون', 75, 70, 65, 55, 45),
                ('Rhaena Targaryen', 'شاهزاده‌خانم', 'Sheepstealer', 'تارگرین', 'دراگون‌استون', 55, 75, 70, 60, 50),
                ('Hugh Hammer', 'اژدهاسوار سیاه‌ها', 'Vermithor', NULL, NULL, 80, 55, 45, 50, 35),
                ('Corlys Velaryon', 'فرمانده ناوگان و لرد مدرفت', NULL, 'ولاریون', 'دراگون‌استون', 78, 88, 90, 95, 50),
                ('Adam Velaryon', 'اژدهاسوار', 'Seasmoke', 'ولاریون', 'دراگون‌استون', 78, 65, 60, 55, 40),
                ('Alyn Velaryon', 'دریانورد و وارث ولاریون', NULL, 'ولاریون', 'دراگون‌استون', 60, 70, 75, 70, 45),
                ('Bartimos Celtigar', 'لرد خاندان سلتیگار', NULL, 'سلتیگار', 'جزیره پنجه', 55, 75, 70, 78, 50),
                ('Lord Reynald Darklyn', 'لرد خاندان دارکلین', NULL, 'دارکلین', 'داسکندیل', 65, 70, 75, 78, 50)
            ON CONFLICT (character_name) DO NOTHING
        """)
        await conn.execute("""
            INSERT INTO character_profiles
                (character_name, biography, title, location, house)
            VALUES
                ('سپتون اعظم',
                 'رهبر عالی ایمان هفتگان و عالی‌ترین مقام مذهبی وستروس.',
                 'سپتون اعظم', 'کینگزلندینگ', 'ایمان هفتگان')
            ON CONFLICT (character_name) DO UPDATE SET
                title = EXCLUDED.title,
                location = EXCLUDED.location,
                house = EXCLUDED.house,
                biography = CASE
                    WHEN character_profiles.biography IS NULL
                      OR character_profiles.biography = 'شرح کامل این شخصیت هنوز توسط مدیر بازی ثبت نشده است.'
                    THEN EXCLUDED.biography
                    ELSE character_profiles.biography
                END,
                updated_at = NOW()
        """)
        # Normalize legacy English spellings to the canonical names used by the
        # selectable character roster. Run before roster seeding so ownership and
        # profile details stay attached to the canonical profile.
        for legacy_name, canonical_name in (
            ("Adam Velaryon", "Addam Velaryon"),
            ("Alf White", "Ulf White"),
            ("Lord Reynald Darklyn", "Ynald Darklyn"),
        ):
            await conn.execute("""
                UPDATE character_profiles AS legacy
                SET character_name = $2, updated_at = NOW()
                WHERE legacy.character_name = $1
                  AND NOT EXISTS (
                      SELECT 1 FROM character_profiles AS canonical
                      WHERE canonical.character_name = $2
                  )
            """, legacy_name, canonical_name)

        # Ensure every character in the bot's registered travel rosters has a
        # ready-to-claim profile, even when no player owns the character yet.
        # Unknown lore fields are explicit placeholders, never guessed facts.
        for castle_name, roster in TRAVEL_CHARACTER_ROSTER.items():
            for roster_entry in roster:
                character_name = str(roster_entry).split("|")[-1].strip()
                if not character_name:
                    continue
                await conn.execute("""
                    INSERT INTO character_profiles
                        (character_name, biography, age, health, title, location,
                         spouse, children, dragon, house)
                    VALUES
                        ($1, 'شرح کامل این شخصیت هنوز توسط مدیر بازی ثبت نشده است.',
                         'نیازمند تعیین', 'نیازمند تعیین', 'نیازمند تعیین', $2,
                         'نیازمند تعیین', 'نیازمند تعیین', 'نیازمند تعیین',
                         'نیازمند تعیین')
                    ON CONFLICT (character_name) DO UPDATE SET
                        biography = COALESCE(character_profiles.biography, EXCLUDED.biography),
                        age = COALESCE(character_profiles.age, EXCLUDED.age),
                        health = COALESCE(character_profiles.health, EXCLUDED.health),
                        title = COALESCE(character_profiles.title, EXCLUDED.title),
                        location = COALESCE(character_profiles.location, EXCLUDED.location),
                        spouse = COALESCE(character_profiles.spouse, EXCLUDED.spouse),
                        children = COALESCE(character_profiles.children, EXCLUDED.children),
                        dragon = COALESCE(character_profiles.dragon, EXCLUDED.dragon),
                        house = COALESCE(character_profiles.house, EXCLUDED.house)
                """, character_name, castle_name)
        # These four characters are not married in the current game timeline.
        # Keep both sides of each pair explicitly unmarried in their public profiles.
        await conn.execute("""
            UPDATE character_profiles
            SET spouse = 'هنوز ازدواج نکرده',
                updated_at = NOW()
            WHERE character_name IN (
                'Rhaenyra Targaryen',
                'Daemon Targaryen',
                'Baela Targaryen',
                'Jacaerys Velaryon'
            )
        """)
        # Daeron's canonical seat is Oldtown; correct any legacy profile location
        # so every public/profile view uses the same castle.
        await conn.execute("""
            UPDATE character_profiles
            SET location = 'اولدتاون', updated_at = NOW()
            WHERE character_name = 'Daeron Targaryen'
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS game_clock (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                game_year INTEGER NOT NULL DEFAULT 129,
                season VARCHAR(20) NOT NULL DEFAULT 'spring',
                last_year_update TIMESTAMPTZ,
                last_season_update TIMESTAMPTZ,
                is_running BOOLEAN NOT NULL DEFAULT FALSE,
                started_at TIMESTAMPTZ,
                elapsed_seconds BIGINT NOT NULL DEFAULT 0,
                CHECK (season IN ('spring', 'summer', 'autumn', 'winter'))
            )
        """)
        await conn.execute("ALTER TABLE game_clock ADD COLUMN IF NOT EXISTS is_running BOOLEAN NOT NULL DEFAULT FALSE")
        await conn.execute("ALTER TABLE game_clock ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ")
        await conn.execute("ALTER TABLE game_clock ADD COLUMN IF NOT EXISTS elapsed_seconds BIGINT NOT NULL DEFAULT 0")
        await conn.execute("""
            INSERT INTO game_clock (id, game_year, season, is_running, started_at, elapsed_seconds)
            VALUES (1, 129, 'spring', FALSE, NULL, 0) ON CONFLICT (id) DO NOTHING
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS game_state_control (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                reset_version BIGINT NOT NULL DEFAULT 0,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            INSERT INTO game_state_control (id, reset_version)
            VALUES (1, 0) ON CONFLICT (id) DO NOTHING
        """)
        await conn.execute(
            "ALTER TABLE game_state_control ADD COLUMN IF NOT EXISTS economy_reset_version BIGINT NOT NULL DEFAULT 0"
        )
        needs_clock_seed = not await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM app_migrations WHERE migration_key = 'game-clock-canon-start-v1')"
        )
        if needs_clock_seed:
            await conn.execute("""
                UPDATE game_clock SET game_year = 129, season = 'spring', is_running = FALSE,
                    started_at = NULL, elapsed_seconds = 0 WHERE id = 1
            """)
            await conn.execute("INSERT INTO app_migrations (migration_key) VALUES ('game-clock-canon-start-v1') ON CONFLICT DO NOTHING")


        await conn.execute("""
            CREATE TABLE IF NOT EXISTS military_campaigns (
                id BIGSERIAL PRIMARY KEY,
                sender_player_id BIGINT NOT NULL REFERENCES players(id),
                sender_house_id BIGINT REFERENCES houses(id),
                commander_player_id BIGINT NOT NULL REFERENCES players(id),
                commander_profile_id BIGINT REFERENCES character_profiles(id),
                commander_name VARCHAR(180) NOT NULL,
                commander_type VARCHAR(20) NOT NULL,
                target VARCHAR(150),
                target_by_commander BOOLEAN NOT NULL DEFAULT FALSE,
                mission VARCHAR(20) NOT NULL,
                troop_count BIGINT NOT NULL CHECK (troop_count > 0),
                status VARCHAR(30) NOT NULL DEFAULT 'pending_commander',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                responded_at TIMESTAMPTZ
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS military_campaigns_parties_idx ON military_campaigns (sender_player_id, commander_player_id, status, created_at DESC)")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS market_listings (
                id BIGSERIAL PRIMARY KEY,
                seller_player_id BIGINT NOT NULL REFERENCES players(id),
                seller_house_id BIGINT NOT NULL REFERENCES houses(id),
                item_name VARCHAR(100) NOT NULL,
                quantity BIGINT NOT NULL CHECK (quantity > 0),
                unit_price BIGINT NOT NULL CHECK (unit_price > 0),
                currency VARCHAR(20) NOT NULL DEFAULT 'سکه',
                note TEXT NOT NULL DEFAULT '',
                status VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'cancelled', 'completed')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS market_listings_active_idx ON market_listings (status, created_at DESC)")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_contracts (
                id BIGSERIAL PRIMARY KEY,
                proposer_player_id BIGINT NOT NULL REFERENCES players(id),
                proposer_house_id BIGINT NOT NULL REFERENCES houses(id),
                recipient_house_id BIGINT NOT NULL REFERENCES houses(id),
                recipient_player_id BIGINT REFERENCES players(id),
                offered_item VARCHAR(100) NOT NULL,
                offered_quantity BIGINT NOT NULL CHECK (offered_quantity > 0),
                requested_item VARCHAR(100) NOT NULL,
                requested_quantity BIGINT NOT NULL CHECK (requested_quantity > 0),
                duration_years INTEGER NOT NULL CHECK (duration_years BETWEEN 1 AND 100),
                penalty_coins BIGINT NOT NULL CHECK (penalty_coins >= 0),
                status VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','accepted','rejected','cancelled','completed','breached')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                responded_at TIMESTAMPTZ
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS trade_contracts_houses_idx ON trade_contracts (proposer_house_id, recipient_house_id, status, created_at DESC)")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS game_letters (
                id BIGSERIAL PRIMARY KEY,
                sender_player_id BIGINT NOT NULL REFERENCES players(id),
                recipient_player_id BIGINT NOT NULL REFERENCES players(id),
                subject VARCHAR(160) NOT NULL,
                body TEXT NOT NULL,
                category VARCHAR(20) NOT NULL DEFAULT 'personal',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                read_at TIMESTAMPTZ,
                is_anonymous BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)
        await conn.execute("ALTER TABLE game_letters ADD COLUMN IF NOT EXISTS is_anonymous BOOLEAN NOT NULL DEFAULT FALSE")
        await conn.execute("CREATE INDEX IF NOT EXISTS game_letters_inbox_idx ON game_letters (recipient_player_id, created_at DESC)")
        await conn.execute("CREATE INDEX IF NOT EXISTS game_letters_outbox_idx ON game_letters (sender_player_id, created_at DESC)")
        # Preserve existing and future player letters; never clear the mailbox at startup.

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS court_appointments (
                castle_name VARCHAR(150) NOT NULL,
                post_key VARCHAR(50) NOT NULL,
                appointee_name VARCHAR(150) NOT NULL,
                appointed_by BIGINT REFERENCES players(id),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (castle_name, post_key)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS character_travels (
                character_name VARCHAR(150) NOT NULL,
                home_castle VARCHAR(150) NOT NULL,
                current_castle VARCHAR(150) NOT NULL,
                travel_type VARCHAR(20) NOT NULL DEFAULT 'temporary'
                    CHECK (travel_type IN ('temporary', 'permanent')),
                last_travel_by BIGINT REFERENCES players(id),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (character_name, home_castle)
            )
        """)
        await conn.execute("ALTER TABLE character_travels ADD COLUMN IF NOT EXISTS travel_type VARCHAR(20) NOT NULL DEFAULT 'temporary'")
        await conn.execute("CREATE INDEX IF NOT EXISTS character_travels_current_idx ON character_travels (current_castle, updated_at DESC)")
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="ورود به بازی",
                web_app=WebAppInfo(url=f"{WEBHOOK_BASE_URL}/play-v5?build=20261106m"),
            )
        )
    except Exception:
        logging.exception("Could not update Telegram app menu button")

    try:
        await bot.set_webhook(WEBHOOK_URL)
    except TelegramRetryAfter as exc:
        logging.warning(
            "Telegram rate-limited setWebhook; retrying in %s seconds",
            exc.retry_after,
        )
        await asyncio.sleep(exc.retry_after + 1)
        try:
            await bot.set_webhook(WEBHOOK_URL)
        except Exception:
            logging.exception(
                "Could not set Telegram webhook after retry; web app will continue starting"
            )
    except Exception:
        logging.exception(
            "Could not set Telegram webhook; web app will continue starting"
        )


async def on_cleanup(app):
    global db_pool
    if app.get("db"):
        await app["db"].close()
    db_pool = None
    await bot.session.close()


async def webapp_fallback_handler(request):
    # Telegram clients may keep an older WebApp path; serve the game shell for
    # unknown browser paths while preserving real 404s for unknown API routes.
    if request.path == WEBHOOK_PATH or request.path.startswith("/api/"):
        raise web.HTTPNotFound()
    logging.warning("WebApp fallback served for path: %s", request.path)
    return await index_handler(request)


def create_app():
    app = web.Application(client_max_size=1024 * 1024)

    app.router.add_get("/", index_handler)
    app.router.add_get("/app", index_handler)
    app.router.add_get("/app-v2", index_handler)
    app.router.add_get("/app-v3", index_handler)
    app.router.add_get("/play-v4", index_handler)
    app.router.add_get("/play-v5", index_handler)

    app.router.add_post("/api/auth/telegram", auth_handler)
    app.router.add_post("/api/auth/desktop/request", desktop_login_request_handler)
    app.router.add_get("/api/auth/desktop/{code}", desktop_login_status_handler)
    app.router.add_get("/api/me", me_handler)
    app.router.add_get("/api/profiles", profiles_list_handler)
    app.router.add_get("/api/profiles/public", public_profiles_list_handler)
    app.router.add_get("/api/profiles/{profile_id}", profile_detail_handler)
    app.router.add_put("/api/admin/profiles/{profile_id}", admin_update_profile_handler)
    app.router.add_put("/api/admin/profiles/{profile_id}/owner", admin_assign_profile_owner_handler)
    app.router.add_get("/api/my-house/state", my_house_state_handler)
    app.router.add_put("/api/my-house/state", my_house_state_update_handler)
    app.router.add_get("/api/game-clock", game_clock_handler)
    app.router.add_get("/api/game-state-control", game_state_control_handler)
    app.router.add_post("/api/admin/game-state/reset", admin_reset_game_state_handler)
    app.router.add_post("/api/admin/economy/reset", admin_reset_economy_handler)
    app.router.add_post("/api/admin/game-clock/start", admin_game_clock_start_handler)
    app.router.add_post("/api/admin/game-clock/pause", admin_game_clock_pause_handler)
    app.router.add_get("/api/military/requests", military_requests_handler)
    app.router.add_post("/api/military/campaigns", military_campaign_create_handler)
    app.router.add_post("/api/military/campaigns/{campaign_id}/respond", military_campaign_respond_handler)
    app.router.add_put("/api/military/campaigns/{campaign_id}/destination", military_campaign_destination_handler)
    app.router.add_get("/api/marriage", marriage_handler)
    app.router.add_post("/api/marriage/proposals", marriage_proposal_create_handler)
    app.router.add_post("/api/marriage/proposals/{proposal_id}/respond", marriage_proposal_respond_handler)
    app.router.add_post("/api/marriage/{marriage_id}/ceremony", marriage_ceremony_handler)
    app.router.add_post("/api/marriage/{marriage_id}/invite", wedding_invite_all_handler)
    app.router.add_post("/api/marriage/invitations/{invitation_id}/respond", wedding_invitation_respond_handler)
    app.router.add_post("/api/marriage/invitations/{invitation_id}/gift", wedding_gift_handler)
    app.router.add_get("/api/family", family_handler)
    app.router.add_get("/api/castles/{castle_name}/members", castle_members_handler)
    app.router.add_get("/api/court/appointments", court_appointments_handler)
    app.router.add_put("/api/court/appointments", court_appointment_update_handler)
    app.router.add_get("/api/court/travel", character_travel_handler)
    app.router.add_put("/api/court/travel", character_travel_update_handler)
    app.router.add_post("/api/family/members/{player_id}", family_add_member_handler)
    app.router.add_delete("/api/family/members/{player_id}", family_remove_member_handler)
    app.router.add_put("/api/admin/players/{player_id}/role", admin_update_player_role_handler)
    app.router.add_put("/api/admin/players/{player_id}/telegram-id", admin_update_player_telegram_id_handler)
    app.router.add_put("/api/admin/players/{player_id}/active", admin_set_player_active_handler)
    app.router.add_post("/api/logout", logout_handler)
    app.router.add_get("/api/admin/players", admin_players_handler)
    app.router.add_get("/api/admin/device-groups", admin_device_groups_handler)
    app.router.add_get("/api/admin/login-requests", admin_login_requests_handler)
    app.router.add_post("/api/admin/login-requests/{telegram_id}/assign", admin_assign_login_request_handler)
    app.router.add_get("/api/admin/houses", admin_houses_handler)
    app.router.add_put("/api/admin/houses/{house_id}/economy", admin_update_house_economy_handler)
    app.router.add_put("/api/admin/players/{player_id}/house", admin_assign_house_handler)
    app.router.add_put("/api/admin/players/{player_id}/castle", admin_assign_castle_handler)
    app.router.add_post("/api/admin/players", admin_add_player_handler)
    app.router.add_get("/api/trade/houses", trade_houses_handler)
    app.router.add_get("/api/trade/contracts", trade_contracts_handler)
    app.router.add_post("/api/trade/contracts", trade_contract_create_handler)
    app.router.add_post("/api/trade/contracts/{contract_id}/respond", trade_contract_respond_handler)
    app.router.add_get("/api/market/listings", market_listings_handler)
    app.router.add_post("/api/market/listings", market_create_listing_handler)
    app.router.add_delete("/api/market/listings/{listing_id}", market_cancel_listing_handler)
    app.router.add_get("/api/mail/players", mail_players_handler)
    app.router.add_get("/api/mail", mail_list_handler)
    app.router.add_get("/api/mail/unread-count", mail_unread_count_handler)
    app.router.add_post("/api/mail", mail_send_handler)
    app.router.add_post("/api/mail/{letter_id}/read", mail_read_handler)
    app.router.add_get("/{tail:.*}", webapp_fallback_handler)

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=WEB_SERVER_PORT)
