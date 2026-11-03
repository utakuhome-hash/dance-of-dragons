import asyncio
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
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application


BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_BASE_URL = os.environ["WEBHOOK_BASE_URL"].rstrip("/")
WEBHOOK_PATH = "/telegram-webhook"
WEBHOOK_URL = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
WEB_SERVER_PORT = int(os.getenv("PORT", "10000"))

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_FILE = BASE_DIR / "static" / "index.html"

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
            SELECT p.id, p.username, p.telegram_id, p.role, p.house_id, p.castle_name,
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
            SELECT p.id, p.username, p.telegram_id, p.role, p.house_id, p.castle_name,
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
            "castle_name": player["castle_name"],
            "house_name": player["house_name"],
            "is_active": player["is_active"],
            "is_super_admin": player["is_super_admin"],
        }
    })


async def castle_members_handler(request):
    castle_name = request.match_info["castle_name"].strip()
    if not castle_name or len(castle_name) > 150:
        return json_error("invalid_castle_name")
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.username, h.name AS house_name
            FROM players p
            LEFT JOIN houses h ON h.id = p.house_id
            WHERE p.is_active = TRUE AND p.castle_name = $1
            ORDER BY p.username
            """,
            castle_name,
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


def can_manage_court(player, castle_name):
    if not player or not player.get("is_active"):
        return False
    if player.get("is_super_admin"):
        return True
    user = normalize_court_name(player.get("username"))
    castle = normalize_court_name(castle_name)
    if castle in (normalize_court_name("کینگزلندینگ"), normalize_court_name("King's Landing")):
        return "اگان" in user or "aegon" in user
    if castle in (normalize_court_name("دراگون‌استون"), normalize_court_name("Dragonstone")):
        return "رینیرا" in user or "rhaenyra" in user
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
    castle_name = str(request.query.get("castle_name") or player.get("castle_name") or "").strip()
    if not castle_name or len(castle_name) > 150:
        return json_error("invalid_castle_name")
    if not player.get("is_super_admin") and normalize_court_name(castle_name) != normalize_court_name(player.get("castle_name")):
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
    castle_name = str(data.get("castle_name") or player.get("castle_name") or "").strip()
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
        "آدام ولاریون | Addam Velaryon"
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
        "سپتون اعظم | The High Septon"
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
            SELECT character_name, home_castle, current_castle, updated_at
            FROM character_travels
            WHERE current_castle = $1 AND home_castle <> current_castle
            ORDER BY character_name
            """,
            castle,
        )
        away_rows = await conn.fetch(
            """
            SELECT character_name, home_castle, current_castle, updated_at
            FROM character_travels
            WHERE home_castle = $1 AND current_castle <> home_castle
            ORDER BY character_name
            """,
            castle,
        )
    return web.json_response({
        "ok": True,
        "castle_name": castle,
        "can_travel": can_travel,
        "destinations": list(TRAVEL_CASTLE_ALIASES.keys()),
        "guests": [
            {
                "character_name": row["character_name"],
                "home_castle": row["home_castle"],
                "current_castle": row["current_castle"],
                "updated_at": row["updated_at"].isoformat(),
            }
            for row in rows
        ],
        "away": [
            {
                "character_name": row["character_name"],
                "home_castle": row["home_castle"],
                "current_castle": row["current_castle"],
                "updated_at": row["updated_at"].isoformat(),
            }
            for row in away_rows
        ],
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
                    (character_name, home_castle, current_castle, last_travel_by, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (character_name, home_castle)
                DO UPDATE SET current_castle = EXCLUDED.current_castle,
                              last_travel_by = EXCLUDED.last_travel_by,
                              updated_at = NOW()
                RETURNING updated_at
                """,
                character_name, home_castle, destination, player["id"],
            )
            updated_at = row["updated_at"].isoformat()
    return web.json_response({
        "ok": True,
        "character_name": character_name,
        "home_castle": home_castle,
        "current_castle": destination,
        "returned_home": destination == home_castle,
        "updated_at": updated_at,
    })


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
                SELECT p.id, p.username, p.telegram_id, p.role, p.house_id, p.castle_name,
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
                    VALUES ($1, '', $2, 'player', NULL, TRUE, NOW(), FALSE)
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
    return {
        "game_year": int(row["game_year"]) + (total_seconds // 86400),
        "season": season_key, "season_label": season_label, "season_icon": season_icon,
        "is_running": bool(row["is_running"]), "total_elapsed_seconds": total_seconds,
        "seconds_until_season": 172800 - (total_seconds % 172800),
        "seconds_until_year": 86400 - (total_seconds % 86400),
    }


async def game_clock_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    async with request.app["db"].acquire() as conn:
        clock = await read_game_clock(conn)
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



async def profiles_list_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    is_admin = bool(player.get("is_super_admin") and player.get("role") == "admin")
    async with request.app["db"].acquire() as conn:
        if is_admin:
            rows = await conn.fetch("""
                SELECT id, character_name, title, location, house, owner_player_id
                FROM character_profiles ORDER BY character_name
            """)
        else:
            # Public profile directory: all players can browse character profiles.
            # Private skills remain protected by profile_detail_handler.
            rows = await conn.fetch("""
                SELECT id, character_name, title, location, house
                FROM character_profiles
                ORDER BY character_name
            """)
        profiles = [dict(row) for row in rows]
        players = []
        if is_admin:
            players = [dict(r) for r in await conn.fetch(
                "SELECT id, username FROM players WHERE is_active = TRUE ORDER BY username"
            )]
    return web.json_response({"ok": True, "profiles": profiles, "is_admin": is_admin, "players": players})


async def public_profiles_list_handler(request):
    player = await get_authenticated_player(request)
    if not player or not player.get("is_active"):
        return json_error("unauthorized", 401)
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, character_name, title, location, house
            FROM character_profiles
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
                   spouse, children, dragon, house, owner_player_id,
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
                updated_at=NOW()
            WHERE id=$16 RETURNING id, character_name
        """, *(values[k] for k in public_fields), owner_id, *skill_values, profile_id)
    if not updated:
        return json_error("profile_not_found", 404)
    return web.json_response({"ok": True, "profile": dict(updated)})

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
        await conn.execute("CREATE INDEX IF NOT EXISTS player_sessions_player_idx ON player_sessions (player_id)")

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
        # Import every character already registered in the bot's travel rosters.
        # Only use facts present in that roster; do not invent ages, biographies,
        # houses, titles, or private skill values.
        for castle_name, roster in TRAVEL_CHARACTER_ROSTER.items():
            for roster_entry in roster:
                character_name = str(roster_entry).split("|")[-1].strip()
                if not character_name:
                    continue
                await conn.execute("""
                    INSERT INTO character_profiles (character_name, location)
                    VALUES ($1, $2)
                    ON CONFLICT (character_name) DO NOTHING
                """, character_name, castle_name)
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
                last_travel_by BIGINT REFERENCES players(id),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (character_name, home_castle)
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS character_travels_current_idx ON character_travels (current_castle, updated_at DESC)")
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


def create_app():
    app = web.Application(client_max_size=1024 * 1024)

    app.router.add_get("/", index_handler)
    app.router.add_get("/app", index_handler)

    app.router.add_post("/api/auth/telegram", auth_handler)
    app.router.add_get("/api/me", me_handler)
    app.router.add_get("/api/profiles", profiles_list_handler)
    app.router.add_get("/api/profiles/public", public_profiles_list_handler)
    app.router.add_get("/api/profiles/{profile_id}", profile_detail_handler)
    app.router.add_put("/api/admin/profiles/{profile_id}", admin_update_profile_handler)
    app.router.add_get("/api/game-clock", game_clock_handler)
    app.router.add_post("/api/admin/game-clock/start", admin_game_clock_start_handler)
    app.router.add_post("/api/admin/game-clock/pause", admin_game_clock_pause_handler)
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
    app.router.add_get("/api/admin/houses", admin_houses_handler)
    app.router.add_put("/api/admin/players/{player_id}/house", admin_assign_house_handler)
    app.router.add_put("/api/admin/players/{player_id}/castle", admin_assign_castle_handler)
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
