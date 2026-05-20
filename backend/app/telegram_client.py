from typing import Any

import httpx


class TelegramClient:
    def __init__(self, *, bot_token: str, api_base: str = "https://api.telegram.org") -> None:
        self.bot_token = bot_token
        self.api_base = api_base.rstrip("/")

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        button_text: str | None = None,
        button_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }

        if button_text:
            callback_data = "open_route"
            if button_payload:
                callback_data = str(button_payload.get("callback_data") or button_payload.get("action") or callback_data)
            payload["reply_markup"] = {
                "inline_keyboard": [[{"text": button_text, "callback_data": callback_data[:64]}]]
            }

        url = f"{self.api_base}/bot{self.bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
