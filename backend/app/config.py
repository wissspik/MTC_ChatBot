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
