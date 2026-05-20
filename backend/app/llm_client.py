from typing import Any

import httpx


class LlmClient:
    def __init__(self, api_llm: str, timeout_seconds: float) -> None:
        self.api_llm = api_llm
        self.timeout_seconds = timeout_seconds

    async def run_prompt(
        self,
        *,
        prompt_name: str,
        prompt: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "prompt_name": prompt_name,
            "prompt": prompt,
            "variables": variables,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.api_llm, json=payload)
            response.raise_for_status()
            data = response.json()

        if isinstance(data, dict) and "output" in data and isinstance(data["output"], dict):
            return data["output"]
        if isinstance(data, dict):
            return data

        raise ValueError("API_LLM returned non-object JSON")
