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


class RoadmapFeedbackRequest(BaseModel):
    telegram_id: int
    roadmap_id: str
    item_ids: list[str] = Field(default_factory=list)
    feedback_type: str = Field(
        pattern="^(useful|not_suitable|too_hard|too_easy|already_completed|change_request)$"
    )
    feedback_text: str | None = None
    max_items_to_change: int = Field(default=2, ge=1, le=2)
    dialog_history: list[dict[str, Any]] = Field(default_factory=list)
    current_datetime: datetime | None = None


class CompleteRoadmapItemRequest(BaseModel):
    telegram_id: int
    item_id: str
    spent_seconds: int = Field(default=0, ge=0)
    answers: list[dict[str, Any]] | dict[str, Any] = Field(default_factory=list)
    note_text: str | None = None
    practice_result: str | None = None
    current_datetime: datetime | None = None


class SendNotificationsRequest(BaseModel):
    telegram_id: int | None = None
    limit: int = Field(default=50, ge=1, le=500)
    dry_run: bool = False
    current_datetime: datetime | None = None


class ApiResponse(BaseModel):
    ok: bool = True
    data: dict[str, Any]
