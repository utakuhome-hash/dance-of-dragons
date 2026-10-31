import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

TOKEN = os.getenv("BOT_TOKEN")
GAME_URL = os.getenv("GAME_URL", "https://example.com")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🐉 ورود به Dance of Dragons",
                    url=GAME_URL
                )
            ]
        ]
    )

    await message.answer(
        "🐉 <b>به دنیای Dance of Dragons خوش آمدی!</b>\n\n"
        "سرنوشت وستروس در دستان خاندان‌هاست.",
        reply_markup=keyboard
    )


async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
