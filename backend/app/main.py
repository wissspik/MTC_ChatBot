import json
from datetime import UTC, datetime, time, timedelta
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.llm_client import LlmClient
from app.prompts import load_prompt, render_prompt
from app.repository import (
    count_sent_pushes_today,
    get_due_motivation_pushes,
    get_roadmap_feedback,
    get_roadmap_for_profile,
    get_roadmap_items,
    get_user_profile,
    insert_llm_run,
    insert_motivation_pushes,
    insert_roadmap_bundle,
    insert_roadmap_feedback,
    mark_motivation_push_status,
    update_roadmap_after_correction,
    update_roadmap_items_after_correction,
    update_user_profile,
    upsert_user_profile,
)
from app.schemas import (
    AnalyzeProfileRequest,
    ApiResponse,
    GenerateRoadmapRequest,
    RoadmapFeedbackRequest,
    SendNotificationsRequest,
)
from app.telegram_client import TelegramClient


app = FastAPI(title="Progressors Learning Backend")


def _jsonable(data: Any) -> Any:
    return jsonable_encoder(data)


def _settings():
    return get_settings()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _parse_hhmm(value: str, fallback: time) -> time:
    try:
        hour, minute = value.split(":", 1)
        return time(hour=int(hour), minute=int(minute))
    except (ValueError, AttributeError):
        return fallback


def _is_quiet_time(now: datetime, settings: dict[str, Any]) -> bool:
    quiet = settings.get("quiet_hours") or {}
    if not quiet.get("enabled", True):
        return False

    start = _parse_hhmm(quiet.get("start", "22:00"), time(22, 0))
    end = _parse_hhmm(quiet.get("end", "09:00"), time(9, 0))
    current = now.time()

    if start <= end:
        return start <= current < end
    return current >= start or current < end


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/profile/analyze", response_model=ApiResponse)
async def analyze_profile(
    request: AnalyzeProfileRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    settings = _settings()
    profile = await upsert_user_profile(
        session,
        telegram_id=request.telegram_id,
        username=request.username,
        first_name=request.first_name,
        last_name=request.last_name,
    )

    prompt_template = load_prompt(settings.prompt_file_path, 1)
    variables = {
        "USER_MESSAGE": request.user_message,
        "USER_PROFILE_ROW_JSON": _jsonable(profile),
        "DIALOG_HISTORY": request.dialog_history,
    }
    prompt = render_prompt(prompt_template, variables)

    llm_client = LlmClient(settings.api_llm, settings.llm_timeout_seconds)
    try:
        llm_output = await llm_client.run_prompt(
            prompt_name="profile_analysis",
            prompt=prompt,
            variables=variables,
        )
    except Exception as exc:
        await insert_llm_run(
            session,
            profile_id=str(profile["user_id"]),
            roadmap_id=None,
            prompt_name="profile_analysis",
            input_json=variables,
            output_json=None,
            status="failed",
            error_text=str(exc),
        )
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc

    profile_update = llm_output.get("User_profile_update") or {}
    updated_profile = await update_user_profile(
        session,
        user_id=str(profile["user_id"]),
        update=profile_update,
    )
    await insert_llm_run(
        session,
        profile_id=str(profile["user_id"]),
        roadmap_id=None,
        prompt_name="profile_analysis",
        input_json=variables,
        output_json=llm_output,
    )

    return ApiResponse(
        data={
            "llm_output": llm_output,
            "user_profile": _jsonable(updated_profile),
        }
    )


@app.post("/api/roadmap/generate", response_model=ApiResponse)
async def generate_roadmap(
    request: GenerateRoadmapRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    settings = _settings()
    profile = await get_user_profile(session, telegram_id=request.telegram_id)
    if not profile:
        raise HTTPException(status_code=404, detail="USER_PROFILE not found")

    prompt_template = load_prompt(settings.prompt_file_path, 2)
    current_datetime = request.current_datetime or datetime.now(UTC)
    variables = {
        "CURRENT_DATETIME": current_datetime.isoformat(),
        "USER_PROFILE_ROW_JSON": _jsonable(profile),
        "DIALOG_HISTORY": request.dialog_history,
    }
    prompt = render_prompt(prompt_template, variables)

    llm_client = LlmClient(settings.api_llm, settings.llm_timeout_seconds)
    try:
        llm_output = await llm_client.run_prompt(
            prompt_name="roadmap_generation",
            prompt=prompt,
            variables=variables,
        )
    except Exception as exc:
        await insert_llm_run(
            session,
            profile_id=str(profile["user_id"]),
            roadmap_id=None,
            prompt_name="roadmap_generation",
            input_json=variables,
            output_json=None,
            status="failed",
            error_text=str(exc),
        )
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc

    profile_update = llm_output.get("User_profile_update") or {}
    updated_profile = await update_user_profile(
        session,
        user_id=str(profile["user_id"]),
        update=profile_update,
    )

    bundle = await insert_roadmap_bundle(
        session,
        profile_id=str(profile["user_id"]),
        roadmap=llm_output.get("Roadmap_insert") or {},
        items=llm_output.get("Roadmap_items_insert") or [],
        pushes=llm_output.get("Motivation_pushes_insert") or [],
    )
    await insert_llm_run(
        session,
        profile_id=str(profile["user_id"]),
        roadmap_id=str(bundle["roadmap"]["roadmap_id"]),
        prompt_name="roadmap_generation",
        input_json=variables,
        output_json=llm_output,
    )

    return ApiResponse(
        data={
            "llm_output": llm_output,
            "user_profile": _jsonable(updated_profile),
            "created": _jsonable(bundle),
        }
    )


@app.post("/api/roadmap/feedback", response_model=ApiResponse)
async def correct_roadmap_by_feedback(
    request: RoadmapFeedbackRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    settings = _settings()
    profile = await get_user_profile(session, telegram_id=request.telegram_id)
    if not profile:
        raise HTTPException(status_code=404, detail="USER_PROFILE not found")

    profile_id = str(profile["user_id"])
    roadmap = await get_roadmap_for_profile(
        session,
        profile_id=profile_id,
        roadmap_id=request.roadmap_id,
    )
    if not roadmap:
        raise HTTPException(status_code=404, detail="ROADMAP not found for this user")

    saved_feedback = await insert_roadmap_feedback(
        session,
        profile_id=profile_id,
        roadmap_id=request.roadmap_id,
        item_ids=request.item_ids,
        feedback_type=request.feedback_type,
        feedback_text=request.feedback_text,
    )

    items = await get_roadmap_items(
        session,
        roadmap_id=request.roadmap_id,
        item_ids=request.item_ids or None,
    )
    if request.item_ids and len(items) != len(set(request.item_ids)):
        raise HTTPException(status_code=404, detail="One or more ROADMAP_ITEM ids were not found")

    feedback_history = await get_roadmap_feedback(
        session,
        roadmap_id=request.roadmap_id,
    )

    prompt_template = load_prompt(settings.prompt_file_path, 3)
    current_datetime = request.current_datetime or datetime.now(UTC)
    user_feedback = {
        "feedback_type": request.feedback_type,
        "feedback_text": request.feedback_text,
        "item_ids": request.item_ids,
        "saved_feedback": _jsonable(saved_feedback),
    }
    variables = {
        "CURRENT_DATETIME": current_datetime.isoformat(),
        "MAX_ITEMS_TO_CHANGE": request.max_items_to_change,
        "USER_PROFILE_ROW_JSON": _jsonable(profile),
        "ROADMAP_ROW_JSON": _jsonable(roadmap),
        "ROADMAP_ITEMS_JSON": _jsonable(items),
        "USER_FEEDBACK_JSON": _jsonable(user_feedback),
        "ROADMAP_FEEDBACK_JSON": _jsonable(feedback_history),
        "DIALOG_HISTORY": request.dialog_history,
    }
    prompt = render_prompt(prompt_template, variables)

    llm_client = LlmClient(settings.api_llm, settings.llm_timeout_seconds)
    try:
        llm_output = await llm_client.run_prompt(
            prompt_name="roadmap_correction",
            prompt=prompt,
            variables=variables,
        )
    except Exception as exc:
        await insert_llm_run(
            session,
            profile_id=profile_id,
            roadmap_id=request.roadmap_id,
            prompt_name="roadmap_correction",
            input_json=variables,
            output_json=None,
            status="failed",
            error_text=str(exc),
        )
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc

    roadmap_update = await update_roadmap_after_correction(
        session,
        roadmap_id=request.roadmap_id,
        roadmap_update=llm_output.get("Roadmap_update") or {},
    )
    changed_items = await update_roadmap_items_after_correction(
        session,
        roadmap_id=request.roadmap_id,
        profile_id=profile_id,
        updates=llm_output.get("Roadmap_items_update") or [],
        max_items=request.max_items_to_change,
    )
    pushes = await insert_motivation_pushes(
        session,
        profile_id=profile_id,
        roadmap_id=request.roadmap_id,
        pushes=llm_output.get("Motivation_pushes_insert") or [],
    )
    await insert_llm_run(
        session,
        profile_id=profile_id,
        roadmap_id=request.roadmap_id,
        prompt_name="roadmap_correction",
        input_json=variables,
        output_json=llm_output,
    )

    return ApiResponse(
        data={
            "saved_feedback": _jsonable(saved_feedback),
            "llm_output": llm_output,
            "updated_roadmap": _jsonable(roadmap_update),
            "changed_items": _jsonable(changed_items),
            "pushes": _jsonable(pushes),
        }
    )


@app.post("/api/notifications/send-due", response_model=ApiResponse)
async def send_due_notifications(
    request: SendNotificationsRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    settings = _settings()
    now = _as_utc(request.current_datetime or datetime.now(UTC))

    if not request.dry_run and not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is required to send notifications")

    pushes = await get_due_motivation_pushes(
        session,
        now=now,
        limit=request.limit,
        telegram_id=request.telegram_id,
    )

    telegram = None
    if not request.dry_run and settings.telegram_bot_token:
        telegram = TelegramClient(
            bot_token=settings.telegram_bot_token,
            api_base=settings.telegram_api_base,
        )

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    results: list[dict[str, Any]] = []

    for push in pushes:
        profile_id = str(push["profile_id"])
        notification_settings = _as_dict(push.get("notification_settings_json"))

        if not notification_settings.get("push_enabled", True):
            if not request.dry_run:
                await mark_motivation_push_status(
                    session,
                    push_id=str(push["push_id"]),
                    status="cancelled",
                    sent_at=None,
                )
            results.append(
                {
                    "push_id": str(push["push_id"]),
                    "telegram_id": push["telegram_id"],
                    "action": "cancelled",
                    "reason": "push_disabled",
                }
            )
            continue

        if _is_quiet_time(now, notification_settings):
            if not request.dry_run:
                await mark_motivation_push_status(
                    session,
                    push_id=str(push["push_id"]),
                    status="skipped_by_quiet_hours",
                    sent_at=None,
                )
            results.append(
                {
                    "push_id": str(push["push_id"]),
                    "telegram_id": push["telegram_id"],
                    "action": "skipped_by_quiet_hours",
                }
            )
            continue

        max_pushes = int(notification_settings.get("max_pushes_per_day") or 3)
        sent_today = await count_sent_pushes_today(
            session,
            profile_id=profile_id,
            day_start=day_start,
            day_end=day_end,
        )
        if sent_today >= max_pushes:
            if not request.dry_run:
                await mark_motivation_push_status(
                    session,
                    push_id=str(push["push_id"]),
                    status="rate_limited",
                    sent_at=None,
                )
            results.append(
                {
                    "push_id": str(push["push_id"]),
                    "telegram_id": push["telegram_id"],
                    "action": "rate_limited",
                    "sent_today": sent_today,
                    "max_pushes_per_day": max_pushes,
                }
            )
            continue

        if request.dry_run:
            results.append(
                {
                    "push_id": str(push["push_id"]),
                    "telegram_id": push["telegram_id"],
                    "action": "would_send",
                    "message_text": push["message_text"],
                    "button_text": push.get("button_text"),
                }
            )
            continue

        try:
            assert telegram is not None
            telegram_response = await telegram.send_message(
                chat_id=int(push["telegram_id"]),
                text=push["message_text"],
                button_text=push.get("button_text"),
                button_payload=_as_dict(push.get("button_payload")),
            )
        except Exception as exc:
            await mark_motivation_push_status(
                session,
                push_id=str(push["push_id"]),
                status="failed",
                sent_at=None,
            )
            results.append(
                {
                    "push_id": str(push["push_id"]),
                    "telegram_id": push["telegram_id"],
                    "action": "failed",
                    "error": str(exc),
                }
            )
            continue

        await mark_motivation_push_status(
            session,
            push_id=str(push["push_id"]),
            status="sent",
            sent_at=now,
        )
        results.append(
            {
                "push_id": str(push["push_id"]),
                "telegram_id": push["telegram_id"],
                "action": "sent",
                "telegram_response": telegram_response,
            }
        )

    return ApiResponse(
        data={
            "dry_run": request.dry_run,
            "requested_telegram_id": request.telegram_id,
            "processed": len(results),
            "results": results,
        }
    )
