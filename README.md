# Прогрессоры

ИИ-помощник для построения персонального трека онлайн-обучения.

Проект сделан для хакатона МТС True Tech Arena. Пользователь заходит в Telegram-бота, отвечает на несколько простых вопросов о цели, уровне и времени на обучение, после чего получает персональный roadmap. В web-приложении он открывает карту обучения, проходит шаги, выполняет мини-проверки знаний, получает XP и видит прогресс в профиле.

## Что умеет проект

- Создает профиль пользователя по ответам в Telegram.
- Уточняет цель обучения, уровень, время в неделю и формат материалов.
- Генерирует персональный roadmap с темами, материалами, практикой и мини-проверками.
- Показывает карту обучения в Telegram WebApp.
- Ведет прогресс пользователя: статусы шагов, XP, streak, уровень, навыки.
- Позволяет корректировать roadmap, если материал слишком сложный, простой или уже знакомый.
- Дает возможность спросить AI-мастера по текущему маршруту.
- Планирует мотивационные уведомления без ночных пушей и спама.

## Структура проекта

```text
backend/        FastAPI backend, работа с БД, LLM, roadmap и прогрессом
frontend/web/   Telegram WebApp на React + Vite
telegram_bot/   Telegram-бот на Aiogram 3
docs/           Документы для презентации и сценарий использования
docker-compose.yml
```

## Быстрый запуск через Docker

Нужны Docker и Docker Compose.

1. Скопируйте пример переменных окружения:

```bash
cp .env.example .env
```

На Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

2. Откройте `.env` и заполните нужные значения:

```text
LLM_API_KEY=ваш_ключ_для_LLM
TELEGRAM_BOT_TOKEN=токен_telegram_бота
WEBAPP_URL=публичная_https_ссылка_на_webapp
```

Для локальной проверки backend можно оставить `TELEGRAM_BOT_TOKEN` пустым, но реальный Telegram-бот без токена не запустится.

3. Запустите backend и PostgreSQL:

```bash
docker compose up --build
```

После запуска backend будет доступен по адресу:

```text
http://localhost:8000
```

Документация API:

```text
http://localhost:8000/docs
```

## Запуск web-приложения

WebApp находится в `frontend/web`.

```bash
cd frontend/web
npm install
npm run dev
```

По умолчанию Vite откроет приложение на:

```text
http://localhost:5173
```

Для проверки без Telegram используется тестовый Telegram ID из переменной:

```text
VITE_DEV_TELEGRAM_ID=123
```

Если backend запущен локально, web-приложение обращается к:

```text
http://localhost:8000
```

## Запуск Telegram-бота

Бот находится в `telegram_bot`.

```bash
cd telegram_bot
cp .env.example .env
pip install -r requirements.txt
python main.py
```

На Windows PowerShell:

```powershell
cd telegram_bot
Copy-Item .env.example .env
pip install -r requirements.txt
python main.py
```

В `telegram_bot/.env` нужно указать:

```text
TELEGRAM_BOT_TOKEN=токен_вашего_бота
BACKEND_URL=http://localhost:8000
WEBAPP_URL=https://публичная_ссылка_на_webapp
```

Важно: для Telegram WebApp нужна публичная HTTPS-ссылка. Для локальной демонстрации можно использовать ngrok или другой туннель.

## Основной пользовательский сценарий

1. Пользователь открывает Telegram-бота и нажимает `/start`.
2. Бот показывает кнопки `Сделать трек` и `Информация`.
3. Пользователь нажимает `Сделать трек`.
4. Бот спрашивает цель, уровень, время на обучение и удобный формат материалов.
5. Backend формирует персональный roadmap.
6. Пользователь открывает карту обучения в WebApp.
7. Пользователь проходит шаги, выполняет мини-проверки и получает XP.
8. В профиле пользователь видит цель, уровень, XP, streak и прогресс по навыкам.
9. Если план не подходит, пользователь отправляет фидбек, и roadmap корректируется.
10. AI-мастер помогает с вопросами по текущему маршруту.

## Основные API

Полный список ручек доступен в Swagger:

```text
http://localhost:8000/docs
```

Ключевые ручки:

- `POST /api/profile/analyze` — анализ сообщения пользователя и сбор профиля.
- `POST /api/roadmap/generate` — генерация roadmap.
- `GET /api/roadmap/current` — получение текущего roadmap.
- `POST /api/roadmap/feedback` — корректировка roadmap по фидбеку.
- `POST /api/ai-master/ask` — вопрос AI-мастеру.
- `POST /api/notifications/send-due` — отправка запланированных уведомлений.

## Переменные окружения

Основные переменные лежат в `.env.example`.

```text
POSTGRES_USER=progressors
POSTGRES_PASSWORD=progressors
POSTGRES_DB=progressors
POSTGRES_PORT=5432

BACKEND_PORT=8000
PUBLIC_BACKEND_URL=http://localhost:8000

LLM_PROVIDER=gemini
LLM_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_API_KEY=
LLM_MODEL=gemini-2.5-flash-lite

TELEGRAM_BOT_TOKEN=
WEBAPP_URL=http://localhost:5173
```

Не коммитьте реальные токены и ключи. В репозитории должны быть только `.env.example`.

## Документы

Сценарий использования бота для презентации находится здесь:

```text
docs/scenario_usage_bot.pdf
```

Скрипт для пересборки PDF:

```bash
python scripts/generate_usage_scenario_pdf.py
```

## Проверка перед сдачей

Перед отправкой в GitLab проверьте:

```bash
docker compose up --build
```

```bash
cd frontend/web
npm install
npm run build
```

```bash
cd telegram_bot
pip install -r requirements.txt
python main.py
```

Если запускаете без реального Telegram-токена, проверяйте backend через Swagger и web-приложение через локальный dev-режим.
