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
