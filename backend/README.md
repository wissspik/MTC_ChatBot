# Backend

FastAPI backend для Telegram-бота образовательных roadmap.

## Запуск

```bash
docker compose up --build
```

API будет доступен на:

```text
http://localhost:8000
```

Postgres поднимется с таблицами из `backend/db/schema.sql`.

## ENV

```text
API_LLM=http://host.docker.internal:8080/dump
TELEGRAM_BOT_TOKEN=123456:telegram-bot-token
TELEGRAM_API_BASE=https://api.telegram.org
POSTGRES_DB=progressors
POSTGRES_USER=progressors
POSTGRES_PASSWORD=progressors
BACKEND_PORT=8000
POSTGRES_PORT=5432
```

`API_LLM` — внешний endpoint LLM. Backend отправляет туда JSON:

```json
{
  "prompt_name": "profile_analysis",
  "prompt": "уже подставленный текст Prompt 1 или Prompt 2",
  "variables": {}
}
```

Ожидаемый ответ:

```json
{
  "output": {}
}
```

Если поле `output` отсутствует, backend воспринимает весь JSON-ответ как ответ LLM.

## Ручка 1: анализ профиля

```http
POST /api/profile/analyze
```

```json
{
  "telegram_id": 123,
  "username": "user",
  "first_name": "User",
  "user_message": "Хочу изучить Python backend, я новичок",
  "dialog_history": []
}
```

Что делает:

- создает или обновляет `user_profile`;
- берет `Prompt 1` из `INSTUC.txt`;
- отправляет prompt + variables на `API_LLM`;
- применяет `User_profile_update`;
- пишет лог в `llm_run`.

## Ручка 2: генерация roadmap

```http
POST /api/roadmap/generate
```

```json
{
  "telegram_id": 123,
  "dialog_history": []
}
```

Что делает:

- берет заполненный `user_profile`;
- берет `Prompt 2` из `INSTUC.txt`;
- отправляет prompt + variables на `API_LLM`;
- сохраняет `roadmap`, `roadmap_item`, `motivation_push`;
- обновляет `user_profile`;
- пишет лог в `llm_run`.

## Ручка 3: фидбек и коррекция roadmap

```http
POST /api/roadmap/feedback
```

```json
{
  "telegram_id": 123,
  "roadmap_id": "uuid",
  "item_ids": ["uuid-1", "uuid-2"],
  "feedback_type": "too_hard",
  "feedback_text": "Эти два шага слишком сложные, хочу проще и больше практики",
  "max_items_to_change": 2,
  "dialog_history": []
}
```

Что делает:

- сохраняет фидбек в `roadmap_feedback`;
- берет `Prompt 3` из `INSTUC.txt`;
- передает LLM текущий `user_profile`, `roadmap`, выбранные `roadmap_item` и историю фидбека;
- LLM может изменить максимум `max_items_to_change`, сейчас 1-2 ноды;
- применяет UPDATE к `roadmap_item`;
- при необходимости обновляет `roadmap.roadmap_json`;
- создает новые `motivation_push`;
- пишет лог в `llm_run` с `prompt_name = roadmap_correction`.

Допустимые `feedback_type`:

```text
useful
not_suitable
too_hard
too_easy
already_completed
change_request
```

## Ручка 4: отправка запланированных уведомлений

```http
POST /api/notifications/send-due
```

Отправить due-пуши всем пользователям:

```json
{
  "limit": 50
}
```

Отправить due-пуши одному пользователю:

```json
{
  "telegram_id": 123,
  "limit": 10
}
```

Проверить без реальной отправки:

```json
{
  "telegram_id": 123,
  "dry_run": true
}
```

Что делает:

- берет `motivation_push` со статусом `planned` и `scheduled_at <= now`;
- если указан `telegram_id`, отправляет только этому пользователю;
- проверяет `push_enabled`;
- соблюдает `quiet_hours`;
- соблюдает `max_pushes_per_day`;
- отправляет сообщение через Telegram Bot API;
- меняет статус на `sent`, `failed`, `rate_limited`, `skipped_by_quiet_hours` или `cancelled`.

Для реальной отправки нужен `TELEGRAM_BOT_TOKEN`. Для `dry_run` токен не нужен.

## Возврат skipped-ноды в маршрут

```http
POST /api/roadmap/item/{item_id}/unskip
```

```json
{
  "telegram_id": 123,
  "start_now": false,
  "note_text": "Вернулся к этому шагу"
}
```

Что делает:

- работает только для `roadmap_item.status = skipped`;
- возвращает ноду в `not_started`;
- если `start_now = true`, сразу ставит `in_progress`;
- очищает `completed_at`;
- возвращает обновленную `roadmap_item` и `progress`.

## Завершение roadmap

```http
POST /api/roadmap/{roadmap_id}/complete
```

```json
{
  "telegram_id": 123,
  "allow_skipped": true,
  "force": false
}
```

Что делает:

- проверяет, что roadmap принадлежит пользователю;
- завершает roadmap статусом `completed`;
- по умолчанию skipped-ноды не блокируют завершение;
- `not_started`, `in_progress`, `pending_check`, `expired`, `replaced` блокируют завершение;
- если `force = true`, завершает roadmap даже с незавершенными нодами;
- возвращает `roadmap`, `progress` и `completion_stats`.

Если есть незавершенные ноды и `force = false`, вернет `409`.
