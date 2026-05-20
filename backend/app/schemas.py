from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalyzeProfileRequest(BaseModel):
    telegram_id: int
    user_message: str = Field(min_length=1)
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    dialog_history: list[dict[str, Any]] = Field(default_factory=list)


class GenerateRoadmapRequest(BaseModel):
    telegram_id: int
    dialog_history: list[dict[str, Any]] = Field(default_factory=list)
    current_datetime: datetime | None = None


class ApiResponse(BaseModel):
    ok: bool = True
    data: dict[str, Any]
