# Progressors Telegram WebApp MVP

MVP для хакатона: Telegram bot на `aiogram 3` и React WebApp на `Vite + TypeScript`.
Все данные моковые, реального backend API, авторизации, Postgres и OpenAI-интеграции нет.

## Запуск web

```bash
cd web
cp .env.example .env
npm install
npm run dev
```

Vite покажет локальный URL. Для Telegram WebApp нужен публичный HTTPS URL, например через ngrok или аналогичный туннель.

Пример через ngrok:

```bash
ngrok http 5173
```

Скопируй HTTPS URL вида `https://abc123.ngrok-free.app` в `bot/.env` как `WEBAPP_URL`.

## Запуск bot

```bash
cd bot
cp .env.example .env
# отредактируй .env: BOT_TOKEN и WEBAPP_URL
pip install aiogram python-dotenv
python main.py
```

`WEBAPP_URL` должен вести на web-приложение без query-параметров. Бот сам добавляет:

- `/?tab=profile`
- `/?tab=roadmap`
- `/?tab=mentor`

## Что внутри

- `/bot/main.py` — Telegram bot с командой `/start` и тремя WebApp-кнопками.
- `/web/src/App.tsx` — мобильный Telegram WebApp-интерфейс с вкладками.
- `/web/src/data/mock.ts` — моковые данные пользователя, навыков, достижений, родмапа и AI-ментора.
- `/web/src/index.css` — dark futuristic UI в стиле Progressors.
