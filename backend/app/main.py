from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.llm_client import LlmClient
from app.prompts import load_prompt, render_prompt
from app.repository import (
    get_roadmap_feedback,
    get_roadmap_for_profile,
    get_roadmap_items,
    get_user_profile,
    insert_llm_run,
    insert_motivation_pushes,
    insert_roadmap_bundle,
    insert_roadmap_feedback,
    update_roadmap_after_correction,
    update_roadmap_items_after_correction,
    update_user_profile,
    upsert_user_profile,
)
from app.schemas import AnalyzeProfileRequest, ApiResponse, GenerateRoadmapRequest, RoadmapFeedbackRequest


app = FastAPI(title="Progressors Learning Backend")


def _jsonable(data: Any) -> Any:
    return jsonable_encoder(data)


def _settings():
    return get_settings()


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
