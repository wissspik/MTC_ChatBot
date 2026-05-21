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


class ProfileUpdateRequest(BaseModel):
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    goal_text: str | None = None
    direction: str | None = None
    specific_track: str | None = None
    target_role: str | None = None
    goal_reason: str | None = None
    current_level: str | None = Field(default=None, pattern="^(beginner|basic|professional)$")
    time_per_week_label: str | None = None
    time_per_week_value: int | None = Field(default=None, ge=0)
    preferred_formats: list[str] | None = None
    wishes: str | None = None
    preference_json: dict[str, Any] | None = None
    notification_settings_json: dict[str, Any] | None = None
    dialog_state: str | None = None
    profile_json: dict[str, Any] | None = None


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


class RoadmapItemResourceProgressRequest(BaseModel):
    telegram_id: int
    resource_id: str
    completed: bool
    current_datetime: datetime | None = None


class RoadmapStatusRequest(BaseModel):
    telegram_id: int
    status: str = Field(pattern="^(draft|active|paused|completed|replaced|archived)$")


class RoadmapSwitchRequest(BaseModel):
    roadmap_id: str


class StartRoadmapItemRequest(BaseModel):
    telegram_id: int


class SkipRoadmapItemRequest(BaseModel):
    telegram_id: int
    reason: str = Field(default="change_request", pattern="^(not_suitable|too_hard|too_easy|already_completed|change_request)$")
    feedback_text: str | None = None
    current_datetime: datetime | None = None


class SendNotificationsRequest(BaseModel):
    telegram_id: int | None = None
    limit: int = Field(default=50, ge=1, le=500)
    dry_run: bool = False
    current_datetime: datetime | None = None


class AiMasterRequest(BaseModel):
    telegram_id: int
    question: str = Field(min_length=1, max_length=2000)
    dialog_history: list[dict[str, Any]] = Field(default_factory=list)
    current_datetime: datetime | None = None


class ApiResponse(BaseModel):
    ok: bool = True
    data: dict[str, Any]
