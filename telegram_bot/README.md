# Telegram Bot

Отдельный Telegram-бот для сценария:

1. Пользователь пишет `/start`.
2. Бот показывает main keyboard: `Сделать трек` и `Инфо`.
3. `Сделать трек` запускает сбор профиля через backend `POST /api/profile/analyze`.
4. Если backend возвращает `Need_question=true`, бот задает следующий уточняющий вопрос.
5. Когда профиль готов, бот вызывает `POST /api/roadmap/generate`.
6. После генерации бот отправляет WebApp-кнопку с фронтендом.

## Локальный запуск

```bash
cd telegram_bot
cp .env.example .env
pip install -r requirements.txt
python main.py
```

В `.env` нужно указать:

```text
TELEGRAM_BOT_TOKEN=...
BACKEND_URL=http://localhost:8000
WEBAPP_URL=https://your-public-webapp-url
```

Для Telegram WebApp нужен публичный HTTPS URL, например через ngrok.

## Запуск вместе со всем проектом

Из корня репозитория:

```bash
docker compose up --build
```

Compose поднимает:

- `postgres`
- `backend`
- `web`
- `telegram_bot`

В корневом `.env` должны быть заданы `TELEGRAM_BOT_TOKEN`, `WEBAPP_URL` и `PUBLIC_BACKEND_URL`.
