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
    get_user_profile,
    insert_llm_run,
    insert_roadmap_bundle,
    update_user_profile,
    upsert_user_profile,
)
from app.schemas import AnalyzeProfileRequest, ApiResponse, GenerateRoadmapRequest


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
