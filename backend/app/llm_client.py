from typing import Any

import httpx

from app.config import get_settings


class LlmClient:
    def __init__(
        self,
        api_llm: str | None = None,
        timeout_seconds: float = 120.0,
        use_local: bool = False,
        local_model_name: str | None = None,
    ) -> None:
        self.api_llm = api_llm
        self.timeout_seconds = timeout_seconds
        self.use_local = use_local
        self.local_model_name = local_model_name or "Qwen/Qwen2.5-7B-Instruct"
        
        if self.use_local:
            from app.llm_local import initialize_local_llm
            initialize_local_llm(self.local_model_name)

    async def run_prompt(
        self,
        *,
        prompt_name: str,
        prompt: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """Run a prompt using either local LLM or HTTP API."""
        if self.use_local:
            return self._run_local_prompt(prompt)
        else:
            return await self._run_http_prompt(prompt)
    
    def _run_local_prompt(self, prompt: str) -> dict[str, Any]:
        """Run prompt using local LLM model."""
        from app.llm_local import run_local_prompt_json
        
        try:
            result = run_local_prompt_json(prompt)
            return result
        except Exception as exc:
            raise ValueError(f"Local LLM error: {exc}") from exc
    
    async def _run_http_prompt(self, prompt: str) -> dict[str, Any]:
        """Run prompt using HTTP API."""
        payload = {
            "prompt": prompt,
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
