from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_PROMPT_FILE_PATH = Path(__file__).resolve().parents[2] / "INSTUC.txt"


class Settings(BaseSettings):
    app_name: str = "progressors-learning-backend"
    database_url: str = Field(
        default="postgresql+asyncpg://progressors:progressors@postgres:5432/progressors",
        alias="DATABASE_URL",
    )
    api_llm: str = Field(default="http://localhost:8080/dump", alias="API_LLM")
    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")
    llm_api_base_url: str = Field(default="https://generativelanguage.googleapis.com/v1beta/openai", alias="LLM_API_BASE_URL")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_model: str = Field(default="gemini-2.5-flash-lite", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    llm_json_mode: bool = Field(default=True, alias="LLM_JSON_MODE")
    use_local_llm: bool = Field(default=False, alias="USE_LOCAL_LLM")
    local_llm_model: str = Field(default="Qwen/Qwen2.5-7B-Instruct", alias="LOCAL_LLM_MODEL")
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_api_base: str = Field(default="https://api.telegram.org", alias="TELEGRAM_API_BASE")
    prompt_file_path: Path = Field(default=DEFAULT_PROMPT_FILE_PATH, alias="PROMPT_FILE_PATH")
    llm_timeout_seconds: float = Field(default=120.0, alias="LLM_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
