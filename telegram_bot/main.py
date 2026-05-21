import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:5173").rstrip("/")

MAKE_TRACK = "🚀 Сделать трек"
INFO = "ℹ️ Инфо"
CANCEL = "↩️ Отмена"
LEGACY_MAKE_TRACK = "Сделать трек"
LEGACY_INFO = "Инфо"
LEGACY_CANCEL = "Отмена"


@dataclass
class TrackSession:
    collecting: bool = False
    dialog_history: list[dict[str, Any]] = field(default_factory=list)


sessions: dict[int, TrackSession] = {}

MAX_PROFILE_HISTORY_MESSAGES = 6
MAX_ROADMAP_HISTORY_MESSAGES = 4
MAX_MESSAGE_CHARS = 500


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MAKE_TRACK)],
            [KeyboardButton(text=INFO)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери, что делаем дальше",
    )


def question_keyboard(buttons: list[str] | None = None, allow_multiple: bool = False) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=button)] for button in buttons or []]
    rows.append([KeyboardButton(text=CANCEL)])
    placeholder = "Можно выбрать несколько вариантов или написать свой ответ" if allow_multiple else "Напиши ответ или нажми кнопку"
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=not allow_multiple,
        input_field_placeholder=placeholder,
    )


def webapp_url(telegram_id: int, tab: str = "roadmap") -> str:
    return f"{WEBAPP_URL}/?{urlencode({'tab': tab, 'telegram_id': telegram_id})}"


def webapp_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗺 Открыть roadmap",
                    web_app=WebAppInfo(url=webapp_url(telegram_id, "roadmap")),
                )
            ],
            [
                InlineKeyboardButton(
                    text="👤 Профиль",
                    web_app=WebAppInfo(url=webapp_url(telegram_id, "profile")),
                )
            ],
        ]
    )


def user_payload(message: Message) -> dict[str, Any]:
    user = message.from_user
    return {
        "telegram_id": user.id if user else message.chat.id,
        "username": user.username if user else None,
        "first_name": user.first_name if user else None,
        "last_name": user.last_name if user else None,
    }


def response_data(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("data") or payload


def normalize_message_text(text: str) -> str:
    text = (text or "").strip()
    if len(text) > MAX_MESSAGE_CHARS:
        text = text[:MAX_MESSAGE_CHARS] + "..."
    return text


def trim_history(history: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return history[-limit:]


async def api_request(method: str, path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=120)
    print("API REQUEST", method, f"{BACKEND_URL}{path}")
    print("PAYLOAD SIZE", len(json.dumps(json_body or {}, ensure_ascii=False)))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.request(method, f"{BACKEND_URL}{path}", json=json_body) as response:
            print("API RESPONSE", response.status, path)
            payload = await response.json(content_type=None)
            if response.status >= 400:
                raise RuntimeError(str(payload.get("detail") or payload))
            return response_data(payload)


def next_question_from(data: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
    llm_output = data.get("llm_output") or data.get("fallback_output") or {}
    need_question = bool(llm_output.get("Need_question"))
    next_question = llm_output.get("Next_question") if isinstance(llm_output, dict) else None
    return need_question, next_question if isinstance(next_question, dict) else None


def unsupported_topic_message(data: dict[str, Any]) -> str | None:
    llm_output = data.get("llm_output") or data.get("fallback_output") or {}
    if not data.get("unsupported_topic") and not llm_output.get("Unsupported_topic"):
        return None

    available = data.get("available_areas") or llm_output.get("Available_areas") or []
    answer = llm_output.get("Answer") or "Пока я не умею собрать хороший трек по этой теме 😔 Но мы можем выбрать одно из доступных направлений."
    if available:
        answer = f"{answer}\n\nМожно начать с этих направлений:\n" + "\n".join(f"• {area}" for area in available)
    return answer


async def finish_roadmap(message: Message, telegram_id: int, state: TrackSession) -> None:
    await message.answer("✅ Профиль собран. Сейчас соберу персональный roadmap и подберу материалы...", reply_markup=ReplyKeyboardRemove())
    data = await api_request(
        "POST",
        "/api/roadmap/generate",
        {
            "telegram_id": telegram_id,
            "dialog_history": trim_history(state.dialog_history, MAX_ROADMAP_HISTORY_MESSAGES),
            "current_datetime": datetime.now(UTC).isoformat(),
        },
    )
    created = data.get("created") or {}
    roadmap = created.get("roadmap") or {}
    title = roadmap.get("title") or "Персональный roadmap"
    state.collecting = False
    state.dialog_history.clear()
    await message.answer(
        f"🎉 Готово: {title}\nОткрой карту и начинай первый шаг.",
        reply_markup=webapp_keyboard(telegram_id),
    )
    await message.answer("Главное меню на месте 👇", reply_markup=main_keyboard())


async def process_profile_answer(message: Message) -> None:
    payload = user_payload(message)
    telegram_id = payload["telegram_id"]
    state = sessions.setdefault(telegram_id, TrackSession(collecting=True))
    user_message = normalize_message_text(message.text or "")

    state.dialog_history.append({"role": "user", "content": user_message})
    state.dialog_history = trim_history(state.dialog_history, MAX_PROFILE_HISTORY_MESSAGES)
    data = await api_request(
        "POST",
        "/api/profile/analyze",
        {
            **payload,
            "user_message": user_message,
            "dialog_history": state.dialog_history,
        },
    )

    unsupported_answer = unsupported_topic_message(data)
    if unsupported_answer:
        state.collecting = False
        state.dialog_history.clear()
        await message.answer(unsupported_answer, reply_markup=main_keyboard())
        return

    need_question, next_question = next_question_from(data)
    if need_question and next_question:
        question_text = next_question.get("Text") or "Уточни, пожалуйста, еще один момент 🙌"
        buttons = next_question.get("Buttons") or []
        allow_multiple = bool(next_question.get("Allow_multiple"))
        await message.answer(
            question_text,
            reply_markup=question_keyboard([str(button) for button in buttons], allow_multiple),
        )
        return

    await finish_roadmap(message, telegram_id, state)


async def start(message: Message) -> None:
    await message.answer(
        "Привет! 👋 Я помогу собрать учебный трек под твою цель, уровень и свободное время.",
        reply_markup=main_keyboard(),
    )


async def show_info(message: Message) -> None:
    await message.answer(
        "Я задам несколько коротких вопросов, соберу профиль и построю roadmap с материалами и практикой. "
        "Потом откроешь карту прогресса в WebApp 🗺",
        reply_markup=main_keyboard(),
    )


async def start_track(message: Message) -> None:
    payload = user_payload(message)
    sessions[payload["telegram_id"]] = TrackSession(
        collecting=True,
        dialog_history=[],
    )
    await message.answer(
        "С чего начнем? Напиши навык или профессию, которую хочешь освоить.\n\nНапример: Python backend, UI/UX, SMM ✍️",
        reply_markup=question_keyboard(),
    )


async def cancel(message: Message) -> None:
    payload = user_payload(message)
    sessions.pop(payload["telegram_id"], None)
    await message.answer("Ок, остановил сбор трека. Можно начать заново в любой момент 👍", reply_markup=main_keyboard())


async def handle_text(message: Message) -> None:
    text = (message.text or "").strip()
    payload = user_payload(message)
    state = sessions.get(payload["telegram_id"])

    if text in {MAKE_TRACK, LEGACY_MAKE_TRACK}:
        await start_track(message)
        return
    if text in {INFO, LEGACY_INFO}:
        await show_info(message)
        return
    if text in {CANCEL, LEGACY_CANCEL}:
        await cancel(message)
        return
    if state and state.collecting:
        try:
            await process_profile_answer(message)
        except asyncio.TimeoutError:
            await message.answer(
                "Генерация заняла слишком много времени 😕 Попробуй чуть короче описать цель или начни заново.",
                reply_markup=main_keyboard(),
            )
        except aiohttp.ClientError as exc:
            await message.answer(
                f"Backend временно недоступен 😕\n\n{exc}",
                reply_markup=main_keyboard(),
            )
        except Exception as exc:
            await message.answer(
                f"Не получилось связаться с backend 😕\n\n{exc}",
                reply_markup=main_keyboard(),
            )
        return

    await message.answer("Выбери действие на клавиатуре 👇", reply_markup=main_keyboard())


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN or BOT_TOKEN is required")

    print("BOT BACKEND_URL =", BACKEND_URL)
    print("BOT WEBAPP_URL =", WEBAPP_URL)

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(start, CommandStart())
    dp.message.register(handle_text, F.text)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
