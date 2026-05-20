from typing import Any

import httpx
import json
import re


class LlmClient:
    def __init__(
        self,
        api_llm: str | None = None,
        timeout_seconds: float = 120.0,
        use_local: bool = False,
        local_model_name: str | None = None,
        provider: str = "openai_compatible",
        api_base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        json_mode: bool = True,
    ) -> None:
        self.api_llm = api_llm
        self.timeout_seconds = timeout_seconds
        self.use_local = use_local
        self.local_model_name = local_model_name or "Qwen/Qwen2.5-7B-Instruct"
        self.provider = (provider or "legacy").strip().lower()
        self.api_base_url = (api_base_url or "").rstrip("/")
        self.api_key = api_key
        self.model = model or "gemini-2.5-flash-lite"
        self.temperature = temperature
        self.json_mode = json_mode

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

        if self.provider in {"openai", "openai_compatible", "groq", "openrouter", "gemini"}:
            return await self._run_openai_compatible_prompt(prompt_name, prompt)

        return await self._run_legacy_http_prompt(prompt)
    
    def _run_local_prompt(self, prompt: str) -> dict[str, Any]:
        """Run prompt using local LLM model."""
        from app.llm_local import run_local_prompt_json
        
        try:
            result = run_local_prompt_json(prompt)
            return result
        except Exception as exc:
            raise ValueError(f"Local LLM error: {exc}") from exc
    
    async def _run_openai_compatible_prompt(self, prompt_name: str, prompt: str) -> dict[str, Any]:
        """Run prompt against a hosted OpenAI-compatible chat completions API."""
        if not self.api_base_url:
            raise ValueError("LLM_API_BASE_URL is required for OpenAI-compatible LLM provider")
        if not self.api_key:
            raise ValueError("LLM_API_KEY is required for external LLM provider")

        system_content = "Return only valid JSON. Do not wrap the response in Markdown."
        if prompt_name == "profile_analysis":
            system_content += (
                " Extract facts exactly from the user message. If the user says they know basics, "
                "set Current_level to basic. If the target track is explicit, do not ask for it again."
            )
        elif prompt_name == "roadmap_generation":
            system_content += (
                " Roadmap_items_insert must contain 8 to 14 items. The last item must be a final "
                "project with Source_type set to project. Motivation_pushes_insert must contain 2 to "
                "4 items. Use exact enum codes from the prompt. Do not return a shortened roadmap."
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
        }
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.api_base_url}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("LLM API returned unexpected chat completion response") from exc

        if not isinstance(content, str):
            raise ValueError("LLM API returned non-text message content")

        return self._parse_json_content(content)

    async def _run_legacy_http_prompt(self, prompt: str) -> dict[str, Any]:
        """Run prompt using the previous custom HTTP API contract."""
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

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        text = content.strip()
        fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL | re.IGNORECASE)
        if fence_match:
            text = fence_match.group(1).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise ValueError("LLM response is not valid JSON") from None
            data = json.loads(text[start : end + 1])

        if not isinstance(data, dict):
            raise ValueError("LLM response JSON must be an object")
        return data
