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
    complete_roadmap_item,
    count_sent_pushes_today,
    get_due_motivation_pushes,
    get_current_roadmap_for_profile,
    get_roadmap_feedback,
    get_roadmap_by_id,
    get_roadmap_item_by_id,
    get_roadmap_for_profile,
    get_roadmap_items,
    get_roadmap_progress,
    get_user_profile,
    insert_llm_run,
    insert_motivation_pushes,
    insert_roadmap_bundle,
    insert_roadmap_feedback,
    list_roadmaps_for_profile,
    mark_motivation_push_status,
    skip_roadmap_item,
    start_roadmap_item,
    update_roadmap_after_correction,
    update_roadmap_items_after_correction,
    update_roadmap_status_for_profile,
    update_user_profile,
    upsert_user_profile,
)
from app.schemas import (
    AnalyzeProfileRequest,
    ApiResponse,
    CompleteRoadmapItemRequest,
    GenerateRoadmapRequest,
    ProfileUpdateRequest,
    RoadmapFeedbackRequest,
    RoadmapStatusRequest,
    SendNotificationsRequest,
    SkipRoadmapItemRequest,
    StartRoadmapItemRequest,
)
from app.telegram_client import TelegramClient


app = FastAPI(title="Progressors Learning Backend")


def _jsonable(data: Any) -> Any:
    return jsonable_encoder(data)


def _settings():
    return get_settings()


async def _profile_or_404(session: AsyncSession, telegram_id: int) -> dict[str, Any]:
    profile = await get_user_profile(session, telegram_id=telegram_id)
    if not profile:
        raise HTTPException(status_code=404, detail="USER_PROFILE not found")
    return profile


def _bounded_limit(value: int, *, default: int = 20, maximum: int = 100) -> int:
    if value < 1:
        return default
    return min(value, maximum)


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

    llm_client = LlmClient(
        api_llm=settings.api_llm,
        timeout_seconds=settings.llm_timeout_seconds,
        use_local=settings.use_local_llm,
        local_model_name=settings.local_llm_model,
        provider=settings.llm_provider,
        api_base_url=settings.llm_api_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        json_mode=settings.llm_json_mode,
    )
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


@app.get("/api/profile/{telegram_id}", response_model=ApiResponse)
async def get_profile(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await get_user_profile(session, telegram_id=telegram_id)
    if not profile:
        raise HTTPException(status_code=404, detail="USER_PROFILE not found")
    profile_payload = _jsonable(profile)
    return ApiResponse(data={"profile": profile_payload, "user_profile": profile_payload})


@app.patch("/api/profile/{telegram_id}", response_model=ApiResponse)
async def patch_profile(
    telegram_id: int,
    request: ProfileUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await _profile_or_404(session, telegram_id)
    updated_profile = await update_user_profile(
        session,
        user_id=str(profile["user_id"]),
        update=request.model_dump(exclude_none=True),
    )
    return ApiResponse(data={"user_profile": _jsonable(updated_profile)})


@app.get("/api/profile/{telegram_id}/state", response_model=ApiResponse)
async def get_profile_state(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await _profile_or_404(session, telegram_id)
    profile_id = str(profile["user_id"])
    roadmap = await get_current_roadmap_for_profile(session, profile_id=profile_id)

    if not roadmap:
        return ApiResponse(
            data={
                "profile": _jsonable(profile),
                "roadmap": None,
                "items": [],
                "progress": None,
                "user_profile": _jsonable(profile),
                "current_roadmap": None,
                "roadmap_items": [],
            }
        )

    roadmap_id = str(roadmap["roadmap_id"])
    items = await get_roadmap_items(session, roadmap_id=roadmap_id)
    progress = await get_roadmap_progress(
        session,
        roadmap_id=roadmap_id,
        profile_id=profile_id,
    )
    return ApiResponse(
        data={
            "profile": _jsonable(profile),
            "roadmap": _jsonable(roadmap),
            "items": _jsonable(items),
            "progress": _jsonable(progress),
            "user_profile": _jsonable(profile),
            "current_roadmap": _jsonable(roadmap),
            "roadmap_items": _jsonable(items),
        }
    )


@app.get("/api/profile/{telegram_id}/roadmaps", response_model=ApiResponse)
async def get_profile_roadmaps(
    telegram_id: int,
    status: str | None = None,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    if status and status not in {"draft", "active", "paused", "completed", "replaced", "archived"}:
        raise HTTPException(status_code=400, detail="Invalid roadmap status")

    profile = await _profile_or_404(session, telegram_id)
    roadmaps = await list_roadmaps_for_profile(
        session,
        profile_id=str(profile["user_id"]),
        status=status,
        limit=_bounded_limit(limit),
    )
    return ApiResponse(
        data={
            "profile": _jsonable(profile),
            "roadmaps": _jsonable(roadmaps),
            "count": len(roadmaps),
            "status_filter": status,
        }
    )


@app.get("/api/profile/{telegram_id}/roadmap/current", response_model=ApiResponse)
async def get_current_roadmap(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await _profile_or_404(session, telegram_id)
    roadmap = await get_current_roadmap_for_profile(
        session,
        profile_id=str(profile["user_id"]),
    )
    if not roadmap:
        raise HTTPException(status_code=404, detail="ACTIVE_ROADMAP not found")

    progress = await get_roadmap_progress(
        session,
        roadmap_id=str(roadmap["roadmap_id"]),
        profile_id=str(profile["user_id"]),
    )
    items = await get_roadmap_items(session, roadmap_id=str(roadmap["roadmap_id"]))
    return ApiResponse(
        data={
            "roadmap": _jsonable(roadmap),
            "items": _jsonable(items),
            "progress": _jsonable(progress),
            "roadmap_items": _jsonable(items),
        }
    )


@app.get("/api/profile/{telegram_id}/progress", response_model=ApiResponse)
async def get_profile_progress(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await _profile_or_404(session, telegram_id)
    roadmap = await get_current_roadmap_for_profile(
        session,
        profile_id=str(profile["user_id"]),
    )
    if not roadmap:
        return ApiResponse(
            data={
                "profile": _jsonable(profile),
                "roadmap": None,
                "progress": None,
                "user_profile": _jsonable(profile),
                "current_roadmap": None,
            }
        )

    progress = await get_roadmap_progress(
        session,
        roadmap_id=str(roadmap["roadmap_id"]),
        profile_id=str(profile["user_id"]),
    )
    return ApiResponse(
        data={
            "profile": _jsonable(profile),
            "roadmap": _jsonable(roadmap),
            "progress": _jsonable(progress),
            "user_profile": _jsonable(profile),
            "current_roadmap": _jsonable(roadmap),
        }
    )


@app.get("/api/roadmap/{roadmap_id}", response_model=ApiResponse)
async def get_roadmap(
    roadmap_id: str,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    roadmap = await get_roadmap_by_id(session, roadmap_id=roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="ROADMAP not found")
    items = await get_roadmap_items(session, roadmap_id=roadmap_id)
    progress = await get_roadmap_progress(
        session,
        roadmap_id=roadmap_id,
        profile_id=str(roadmap["profile_id"]),
    )
    feedback = await get_roadmap_feedback(session, roadmap_id=roadmap_id)
    return ApiResponse(
        data={
            "roadmap": _jsonable(roadmap),
            "items": _jsonable(items),
            "progress": _jsonable(progress),
            "feedback": _jsonable(feedback),
            "roadmap_items": _jsonable(items),
            "roadmap_feedback": _jsonable(feedback),
        }
    )


@app.patch("/api/roadmap/{roadmap_id}/status", response_model=ApiResponse)
async def patch_roadmap_status(
    roadmap_id: str,
    request: RoadmapStatusRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await _profile_or_404(session, request.telegram_id)
    roadmap = await update_roadmap_status_for_profile(
        session,
        profile_id=str(profile["user_id"]),
        roadmap_id=roadmap_id,
        status=request.status,
    )
    if not roadmap:
        raise HTTPException(status_code=404, detail="ROADMAP not found for this user")
    return ApiResponse(data={"roadmap": _jsonable(roadmap)})


@app.get("/api/roadmap/{roadmap_id}/items", response_model=ApiResponse)
async def get_roadmap_items_endpoint(
    roadmap_id: str,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    roadmap = await get_roadmap_by_id(session, roadmap_id=roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="ROADMAP not found")

    items = await get_roadmap_items(session, roadmap_id=roadmap_id)
    return ApiResponse(
        data={
            "roadmap": _jsonable(roadmap),
            "items": _jsonable(items),
            "count": len(items),
            "roadmap_items": _jsonable(items),
        }
    )


@app.get("/api/roadmap/{roadmap_id}/feedback", response_model=ApiResponse)
async def get_roadmap_feedback_endpoint(
    roadmap_id: str,
    limit: int = 30,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    roadmap = await get_roadmap_by_id(session, roadmap_id=roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="ROADMAP not found")

    feedback = await get_roadmap_feedback(
        session,
        roadmap_id=roadmap_id,
        limit=_bounded_limit(limit, default=30),
    )
    return ApiResponse(
        data={
            "roadmap": _jsonable(roadmap),
            "feedback": _jsonable(feedback),
            "count": len(feedback),
            "roadmap_feedback": _jsonable(feedback),
        }
    )


@app.get("/api/roadmap/{roadmap_id}/item/{item_id}/test", response_model=ApiResponse)
async def get_roadmap_item_test(
    roadmap_id: str,
    item_id: str,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    item = await get_roadmap_item_by_id(
        session,
        item_id=item_id,
        roadmap_id=roadmap_id,
    )
    if not item:
        raise HTTPException(status_code=404, detail="ROADMAP_ITEM not found")

    test_payload = {
        "item_id": str(item["item_id"]),
        "roadmap_id": str(item["roadmap_id"]),
        "name": item.get("name"),
        "description": item.get("description"),
        "resources": item.get("resources"),
        "completion_check_type": item.get("completion_check_type"),
        "completion_check_json": item.get("completion_check_json"),
        "self_check_questions": item.get("self_check_questions"),
        "min_seconds_before_complete": item.get("min_seconds_before_complete"),
        "xp": item.get("xp"),
        "xp_policy_json": item.get("xp_policy_json"),
    }
    return ApiResponse(data={"mini_test": _jsonable(test_payload)})


@app.post("/api/roadmap/item/{item_id}/start", response_model=ApiResponse)
async def start_item(
    item_id: str,
    request: StartRoadmapItemRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await _profile_or_404(session, request.telegram_id)
    item = await start_roadmap_item(
        session,
        item_id=item_id,
        profile_id=str(profile["user_id"]),
    )
    if not item:
        raise HTTPException(status_code=404, detail="ROADMAP_ITEM not found for this user")
    return ApiResponse(data={"roadmap_item": _jsonable(item)})


@app.post("/api/roadmap/item/{item_id}/skip", response_model=ApiResponse)
async def skip_item(
    item_id: str,
    request: SkipRoadmapItemRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await _profile_or_404(session, request.telegram_id)
    item = await skip_roadmap_item(
        session,
        item_id=item_id,
        profile_id=str(profile["user_id"]),
        note_text=request.feedback_text,
        current_datetime=request.current_datetime,
    )
    if not item:
        raise HTTPException(status_code=404, detail="ROADMAP_ITEM not found for this user")

    feedback = await insert_roadmap_feedback(
        session,
        profile_id=str(profile["user_id"]),
        roadmap_id=str(item["roadmap_id"]),
        item_ids=[str(item["item_id"])],
        feedback_type=request.reason,
        feedback_text=request.feedback_text,
    )
    return ApiResponse(
        data={
            "roadmap_item": _jsonable(item),
            "roadmap_feedback": _jsonable(feedback),
        }
    )


@app.post("/api/roadmap/item/complete", response_model=ApiResponse)
async def complete_item(
    request: CompleteRoadmapItemRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await get_user_profile(session, telegram_id=request.telegram_id)
    if not profile:
        raise HTTPException(status_code=404, detail="USER_PROFILE not found")
    
    profile_id = str(profile["user_id"])
    
    # Complete the item and calculate XP
    completed_item = await complete_roadmap_item(
        session,
        item_id=request.item_id,
        profile_id=profile_id,
        spent_seconds=request.spent_seconds,
        answers=request.answers,
        note_text=request.note_text,
        practice_result=request.practice_result,
        current_datetime=request.current_datetime or datetime.now(UTC),
    )
    
    if not completed_item:
        raise HTTPException(status_code=404, detail="ROADMAP_ITEM not found for this user")
    
    # Fetch updated profile to return current XP
    updated_profile = await get_user_profile(session, telegram_id=request.telegram_id)
    
    return ApiResponse(
        data={
            "completed_item": _jsonable(completed_item),
            "user_profile": _jsonable(updated_profile),
            "xp_earned": {
                "pending_xp": completed_item.get("pending_xp", 0),
                "status": completed_item.get("status"),
                "global_xp": updated_profile.get("global_xp") if updated_profile else 0,
            },
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

    llm_client = LlmClient(
        api_llm=settings.api_llm,
        timeout_seconds=settings.llm_timeout_seconds,
        use_local=settings.use_local_llm,
        local_model_name=settings.local_llm_model,
        provider=settings.llm_provider,
        api_base_url=settings.llm_api_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        json_mode=settings.llm_json_mode,
    )
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

    llm_client = LlmClient(
        api_llm=settings.api_llm,
        timeout_seconds=settings.llm_timeout_seconds,
        use_local=settings.use_local_llm,
        local_model_name=settings.local_llm_model,
        provider=settings.llm_provider,
        api_base_url=settings.llm_api_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        json_mode=settings.llm_json_mode,
    )
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
