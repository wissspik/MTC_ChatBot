# Progressors Telegram WebApp

Фронтенд состоит из двух частей:

- `web` - React WebApp на Vite.
- `bot` - Telegram-бот на aiogram, который собирает профиль, вызывает backend и открывает WebApp с готовым roadmap.

## Запуск WebApp

```bash
cd frontend/web
cp .env.example .env
npm install
npm run dev
```

Для Telegram WebApp нужен публичный HTTPS URL. Локально можно открыть Vite через ngrok или аналогичный туннель:

```bash
ngrok http 5173
```

Полученный URL укажи в `frontend/bot/.env` как `WEBAPP_URL`.

## Запуск бота

```bash
cd frontend/bot
cp .env.example .env
pip install -r requirements.txt
python main.py
```

В `.env` нужны:

- `TELEGRAM_BOT_TOKEN` - токен Telegram-бота.
- `BACKEND_URL` - адрес backend API, например `http://localhost:8000`.
- `WEBAPP_URL` - адрес WebApp без query-параметров.

Бот сам добавляет к ссылке `tab` и `telegram_id`, например:

```text
/?tab=roadmap&telegram_id=123
```

## Docker Compose

Из корня проекта:

```bash
docker compose up --build
```

Сервис `telegram_bot` собирается из `frontend/bot`.
