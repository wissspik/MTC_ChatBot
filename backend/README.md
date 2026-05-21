# Backend

FastAPI backend для проекта «Прогрессоры».

Backend отвечает за хранение профиля пользователя, генерацию roadmap, работу с прогрессом, XP, мини-проверками, AI-мастером и уведомлениями.

## Что внутри

- `FastAPI` — HTTP API.
- `PostgreSQL` — база данных.
- `SQLAlchemy async` — работа с БД.
- `LLM client` — обращение к внешней LLM или локальной модели.
- `Telegram client` — отправка уведомлений через Telegram Bot API.

## Запуск через Docker

Из корня проекта:

```bash
cp .env.example .env
docker compose up --build
```

На Windows PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

После запуска:

```text
Backend: http://localhost:8000
Swagger: http://localhost:8000/docs
PostgreSQL: localhost:5432
```

## Переменные окружения

Минимальные переменные для локального запуска:

```text
POSTGRES_USER=progressors
POSTGRES_PASSWORD=progressors
POSTGRES_DB=progressors
POSTGRES_PORT=5432

BACKEND_PORT=8000

LLM_PROVIDER=gemini
LLM_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_API_KEY=
LLM_MODEL=gemini-2.5-flash-lite

TELEGRAM_BOT_TOKEN=
TELEGRAM_API_BASE=https://api.telegram.org
```

Если `TELEGRAM_BOT_TOKEN` пустой, backend можно тестировать через Swagger, но реальные Telegram-уведомления отправляться не будут.

## Основные API

### Анализ профиля пользователя

```http
POST /api/profile/analyze
```

Пример запроса:

```json
{
  "telegram_id": 123,
  "username": "user",
  "first_name": "User",
  "user_message": "Хочу стать Python backend-разработчиком, я новичок",
  "dialog_history": []
}
```

Что делает:

- создает или обновляет профиль пользователя;
- извлекает цель, уровень, время и предпочтения;
- если данных не хватает, возвращает следующий вопрос;
- если профиль готов, разрешает генерацию roadmap.

### Генерация roadmap

```http
POST /api/roadmap/generate
```

Пример запроса:

```json
{
  "telegram_id": 123,
  "dialog_history": []
}
```

Что делает:

- берет заполненный профиль пользователя;
- формирует персональный roadmap;
- сохраняет маршрут и шаги в БД;
- создает задания, вопросы самопроверки и правила XP;
- планирует мотивационные уведомления.

### Получение текущего roadmap

```http
GET /api/roadmap/current?telegram_id=123
```

Возвращает текущий маршрут, шаги и прогресс пользователя.

### Фидбек и коррекция roadmap

```http
POST /api/roadmap/feedback
```

Пример:

```json
{
  "telegram_id": 123,
  "roadmap_id": "uuid",
  "item_ids": ["uuid-1"],
  "feedback_type": "too_hard",
  "feedback_text": "Этот шаг слишком сложный, хочу проще и больше практики",
  "max_items_to_change": 2,
  "dialog_history": []
}
```

Допустимые `feedback_type`:

```text
useful
not_suitable
too_hard
too_easy
already_completed
change_request
```

### AI-мастер

```http
POST /api/ai-master/ask
```

AI-мастер отвечает на вопросы пользователя по его текущему профилю, roadmap и прогрессу.

### Уведомления

```http
POST /api/notifications/send-due
```

Отправляет запланированные мотивационные пуши. Поддерживает `dry_run`, чтобы проверить логику без реальной отправки.

Пример:

```json
{
  "telegram_id": 123,
  "limit": 10,
  "dry_run": true
}
```

## Мини-проверки и XP

Каждый шаг roadmap может содержать мини-проверку:

- короткие вопросы по теме;
- открытый ответ;
- практическое задание;
- чеклист результата.

XP начисляется не просто за нажатие кнопки, а за подтвержденное прохождение шага. Это делает прогресс честнее: пользователь изучает материал, выполняет действие и только потом получает награду.

## Локальный запуск без Docker

Нужен Python 3.11+ и запущенный PostgreSQL.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Для Linux/macOS активация окружения:

```bash
source .venv/bin/activate
```

Перед запуском задайте `DATABASE_URL` или используйте переменные из `.env.example`.
