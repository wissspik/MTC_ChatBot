import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://example.com")
print("WEBAPP_URL =", WEBAPP_URL)

def webapp_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="Профиль",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?tab=profile"),
            )
        ],
        [
            InlineKeyboardButton(
                text="Открыть карту",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?tab=roadmap"),
            )
        ],
        [
            InlineKeyboardButton(
                text="AI-мастер",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?tab=mentor"),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def start(message: Message) -> None:
    await message.answer(
        "Привет! Я помогу собрать персональный трек развития и прокачивать навыки как в игре.",
        reply_markup=webapp_keyboard(),
    )


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is required")

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(start, CommandStart())
    dp.message.register(start, F.text == "/start")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
