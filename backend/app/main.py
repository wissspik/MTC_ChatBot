import difflib
import hashlib
import json
import re
from datetime import UTC, datetime, time, timedelta
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_master import (
    build_ai_master_context,
    build_ai_master_fallback,
    build_ai_master_prompt,
    validate_ai_master_output,
)
from app.config import get_settings
from app.classifier import (
    build_profile_snapshot,
    build_unsupported_topic_output,
    classify_followup_answer,
    get_next_profile_question,
    guard_profile_topic,
    is_supported_profile_goal,
    merge_profile_updates,
)
from app.db import ensure_db_compat, get_session
from app.llm_client import LlmClient
from app.prompts import load_prompt, render_prompt
from app.resource_guard import guard_roadmap_items
from app.repository import (
    complete_roadmap_for_profile,
    complete_roadmap_item,
    count_sent_pushes_today,
    get_due_motivation_pushes,
    get_current_roadmap_for_profile,
    get_roadmap_feedback,
    get_roadmap_by_id,
    get_roadmap_item_by_id,
    get_roadmap_item_resources,
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
    set_roadmap_item_resource_progress,
    unskip_roadmap_item,
    update_roadmap_after_correction,
    update_roadmap_items_after_correction,
    update_roadmap_status_for_profile,
    update_user_profile,
    upsert_user_profile,
)
from app.roadmap_templates import build_template_roadmap
from app.schemas import (
    AiMasterRequest,
    AnalyzeProfileRequest,
    ApiResponse,
    CompleteRoadmapRequest,
    CompleteRoadmapItemRequest,
    GenerateRoadmapRequest,
    ProfileUpdateRequest,
    RoadmapItemResourceProgressRequest,
    RoadmapFeedbackRequest,
    RoadmapStatusRequest,
    RoadmapSwitchRequest,
    SendNotificationsRequest,
    SkipRoadmapItemRequest,
    StartRoadmapItemRequest,
    UnskipRoadmapItemRequest,
)
from app.telegram_client import TelegramClient
from app.trained_classifier import classify_profile_message_ml as classify_profile_message


app = FastAPI(title="Progressors Learning Backend")

settings = get_settings()
cors_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    await ensure_db_compat()


def _jsonable(data: Any) -> Any:
    return jsonable_encoder(data)


def _settings():
    return get_settings()


async def _profile_or_404(session: AsyncSession, telegram_id: int) -> dict[str, Any]:
    profile = await get_user_profile(session, telegram_id=telegram_id)
    if not profile:
        raise HTTPException(status_code=404, detail="USER_PROFILE not found")
    return profile


async def _insert_llm_run_best_effort(
    session: AsyncSession,
    *,
    profile_id: str | None,
    roadmap_id: str | None,
    prompt_name: str,
    input_json: dict[str, Any],
    output_json: dict[str, Any] | None,
    status: str = "success",
    error_text: str | None = None,
) -> None:
    try:
        await insert_llm_run(
            session,
            profile_id=profile_id,
            roadmap_id=roadmap_id,
            prompt_name=prompt_name,
            input_json=input_json,
            output_json=output_json,
            status=status,
            error_text=error_text,
        )
    except Exception:
        await session.rollback()


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


GENERIC_CHECKPOINT_TITLES = {
    "основы",
    "практика",
    "обучение",
    "развитие",
    "следующий шаг",
    "basics",
    "practice",
    "learning",
    "development",
    "next step",
}
ROADMAP_SOURCE_TYPES = {"article", "text", "practice", "course", "project"}
ROADMAP_COMPLETION_TYPES = {"self_check", "quiz", "practice", "note", "project"}


def _profile_goal_message(profile: dict[str, Any]) -> str:
    parts = [
        profile.get("goal_text"),
        profile.get("direction"),
        profile.get("specific_track"),
        profile.get("target_role"),
        profile.get("goal_reason"),
        profile.get("wishes"),
    ]
    return " ".join(str(part) for part in parts if part)


def _roadmap_domain_decision(profile: dict[str, Any]) -> dict[str, Any]:
    classifier_output = classify_profile_message(_profile_goal_message(profile))
    classifier_update = classifier_output.get("User_profile_update") or {}
    profile_snapshot = build_profile_snapshot(profile, classifier_update)
    domain = profile_snapshot.get("specific_track") or profile_snapshot.get("direction")
    supported = bool(domain) and is_supported_profile_goal(profile_snapshot)
    return {
        "supported": supported,
        "domain": str(domain) if domain else None,
        "classifier_output": classifier_output,
        "profile_snapshot": profile_snapshot,
    }


def _build_unsupported_goal_output(profile: dict[str, Any], reason: str) -> dict[str, Any]:
    understood = _profile_goal_message(profile) or str(profile.get("telegram_id") or "")
    output = build_unsupported_topic_output(understood, reason=reason)
    output["Action"] = "unsupported_goal"
    output["Unsupported_goal"] = True
    return output


def _roadmap_style_seed(profile: dict[str, Any], current_datetime: datetime) -> str:
    seed_input = "|".join(
        [
            str(profile.get("user_id") or profile.get("telegram_id") or ""),
            str(profile.get("goal_text") or ""),
            current_datetime.isoformat(),
        ]
    )
    return hashlib.sha256(seed_input.encode("utf-8")).hexdigest()[:10]


def _compact_profile_for_prompt(profile: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "goal_text",
        "direction",
        "specific_track",
        "target_role",
        "goal_reason",
        "current_level",
        "time_per_week_label",
        "time_per_week_value",
        "preferred_formats",
        "wishes",
        "preference_json",
    )
    return {key: _jsonable(profile.get(key)) for key in keys if profile.get(key) not in (None, "", [], {})}


def _build_roadmap_prompt(
    *,
    profile: dict[str, Any],
    domain: str,
    current_datetime: datetime,
    style_seed: str,
    validation_errors: list[str] | None = None,
) -> str:
    profile_json = json.dumps(_compact_profile_for_prompt(profile), ensure_ascii=False, default=str)
    retry_text = ""
    if validation_errors:
        retry_text = (
            "\nFIX THESE VALIDATION ERRORS: "
            + json.dumps(validation_errors, ensure_ascii=False)
            + "\nReturn a corrected full JSON object only."
        )
    checkpoints_schema = [
        {
            "id": f"step-{index}",
            "title": "",
            "status": "current" if index == 1 else "locked",
            "progress": 40 if index == 1 else 0,
        }
        for index in range(1, 9)
    ]
    checkpoints_schema.append({"id": "goal", "title": "", "status": "goal", "progress": 0})
    item_schema = [
        {
            "Step_order": index,
            "Skill_name": "",
            "Topic_name": "",
            "Name": "",
            "Description": "",
            "Resources": "",
            "Source_type": "project" if index == 8 else "practice",
            "Completion_check_type": "project" if index == 8 else "practice",
            "Practice_task": "",
            "Item_json": {"search_query": "", "checkpoint_id": f"step-{index}"},
        }
        for index in range(1, 9)
    ]
    output_schema = {
        "User_profile_update": {"Dialog_state": "roadmap_ready"},
        "Roadmap_insert": {
            "Title": "",
            "Direction": "",
            "Target_role": "",
            "Level": "",
            "Estimated_duration_weeks": 4,
            "Hours_per_week_label": "",
            "Route_logic": "qwen_domain_roadmap",
            "Status": "active",
            "Version": 1,
            "Roadmap_json": {
                "domain": domain,
                "style_seed": style_seed,
                "checkpoints": checkpoints_schema,
            },
        },
        "Roadmap_items_insert": item_schema,
        "Motivation_pushes_insert": [],
    }
    output_schema_json = json.dumps(output_schema, ensure_ascii=False, separators=(",", ":"))

    return f"""
Return only valid JSON. No markdown.
Language: Russian.
Domain lock: supported_domain="{domain}". Every step, title, task, and final project must stay inside this domain only.
Do not create a roadmap for unrelated wishes. Do not invent URLs: set Resources="" and put search_query in Item_json.
Time: {current_datetime.isoformat()}
Style seed: {style_seed}. Use it to vary wording, examples, project theme, and checkpoint titles.

Profile JSON:
{profile_json}

Rules:
- Exactly 8 Roadmap_items_insert objects, Step_order 1..8.
- Last item Source_type="project"; other Source_type is article, text, practice, or course.
- Names and checkpoint titles must be concrete and unique.
- Forbidden titles: Основы, Практика, Обучение, Развитие, Следующий шаг.
- Roadmap_json.domain="{domain}" and Roadmap_json.style_seed="{style_seed}".
- Roadmap_json.checkpoints has exactly 9 objects: step-1..step-8 plus goal.
- Exactly one current checkpoint, progress 20..80. Locked progress=0. Completed progress=100. Last checkpoint status="goal".

Fill semantic empty strings in this JSON shape. Keep Resources="" unless a free existing URL is certain.
Do not add other top-level keys.
{output_schema_json}
{retry_text}
""".strip()


def _normalize_title(value: Any) -> str:
    text = str(value or "").casefold().replace("ё", "е")
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-zа-я]+", " ", text)).strip()


def _checkpoint_title(value: dict[str, Any]) -> str:
    return str(value.get("title") or value.get("Name") or value.get("name") or "").strip()


def _item_title(value: dict[str, Any]) -> str:
    return str(value.get("Name") or value.get("title") or value.get("name") or "").strip()


def _domain_goal_title(profile: dict[str, Any], domain: str) -> str:
    return str(profile.get("target_role") or profile.get("goal_text") or domain or "goal").strip()


def _derive_checkpoints(output: dict[str, Any], *, domain: str) -> list[dict[str, Any]]:
    roadmap = output.get("Roadmap_insert") if isinstance(output.get("Roadmap_insert"), dict) else {}
    roadmap_json = roadmap.get("Roadmap_json") if isinstance(roadmap.get("Roadmap_json"), dict) else {}
    checkpoints = roadmap_json.get("checkpoints")
    if isinstance(checkpoints, list) and checkpoints:
        return [checkpoint for checkpoint in checkpoints if isinstance(checkpoint, dict)]

    items = output.get("Roadmap_items_insert") if isinstance(output.get("Roadmap_items_insert"), list) else []
    derived: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        step_order = item.get("Step_order") or index
        status = "current" if index == 1 else "locked"
        derived.append(
            {
                "id": f"{domain}-{step_order}",
                "title": _item_title(item),
                "status": status,
                "progress": 40 if status == "current" else 0,
            }
        )
    derived.append(
        {
            "id": f"{domain}-goal",
            "title": str(roadmap.get("Target_role") or roadmap.get("Title") or domain),
            "status": "goal",
            "progress": 0,
        }
    )
    return derived


def _validate_titles(titles: list[str], prefix: str) -> list[str]:
    errors: list[str] = []
    normalized: list[str] = []
    seen: set[str] = set()
    for index, title in enumerate(titles, start=1):
        norm = _normalize_title(title)
        if not norm:
            errors.append(f"{prefix}_title_missing:{index}")
            continue
        generic_prefix = any(
            norm.startswith(f"{generic} ")
            for generic in GENERIC_CHECKPOINT_TITLES
            if len(generic.split()) == 1
        )
        if norm in GENERIC_CHECKPOINT_TITLES or generic_prefix:
            errors.append(f"{prefix}_title_generic:{index}:{title}")
        if norm in seen:
            errors.append(f"{prefix}_title_duplicate:{index}:{title}")
        seen.add(norm)
        normalized.append(norm)

    for left_index, left in enumerate(normalized):
        for right_index, right in enumerate(normalized[left_index + 1 :], start=left_index + 2):
            if len(left) < 6 or len(right) < 6:
                continue
            if difflib.SequenceMatcher(None, left, right).ratio() >= 0.86:
                errors.append(f"{prefix}_title_too_similar:{left_index + 1}:{right_index}")
    return errors


def _roadmap_output_validation_errors(output: dict[str, Any], *, domain: str | None = None) -> list[str]:
    errors: list[str] = []

    if not isinstance(output.get("Roadmap_insert"), dict):
        errors.append("roadmap_insert_missing")
    else:
        roadmap_json = _as_dict(output["Roadmap_insert"].get("Roadmap_json"))
        output_domain = roadmap_json.get("domain") or roadmap_json.get("supported_domain")
        if domain and output_domain and str(output_domain) != domain:
            errors.append(f"domain_mismatch:{output_domain}")

    items = output.get("Roadmap_items_insert")
    if not isinstance(items, list):
        errors.append("roadmap_items_insert_not_list")
        return errors

    if len(items) < 8:
        errors.append(f"roadmap_items_too_short:{len(items)}")
    if len(items) > 14:
        errors.append(f"roadmap_items_too_long:{len(items)}")

    if items:
        last_item = items[-1] if isinstance(items[-1], dict) else {}
        last_source_type = str(last_item.get("Source_type") or "").strip().lower()
        if last_source_type != "project":
            errors.append("final_item_must_be_project")

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"roadmap_item_not_object:{index}")
            continue
        if item.get("Step_order") in [other.get("Step_order") for other in items[: index - 1] if isinstance(other, dict)]:
            errors.append(f"roadmap_item_step_order_duplicate:{index}")
        for field in ("Step_order", "Skill_name", "Name", "Source_type", "Completion_check_type"):
            if item.get(field) in (None, "", []):
                errors.append(f"roadmap_item_missing_{field}:{index}")

    item_titles = [_item_title(item) for item in items if isinstance(item, dict)]
    errors.extend(_validate_titles(item_titles, "roadmap_item"))

    checkpoints = _derive_checkpoints(output, domain=domain or "domain")
    if not checkpoints:
        errors.append("checkpoints_missing")
        return errors
    if isinstance(items, list) and len(checkpoints) != len(items) + 1:
        errors.append(f"checkpoint_count_mismatch:{len(checkpoints)}:{len(items) + 1}")

    checkpoint_ids: set[str] = set()
    current_count = 0
    for index, checkpoint in enumerate(checkpoints, start=1):
        checkpoint_id = str(checkpoint.get("id") or "").strip()
        if not checkpoint_id:
            errors.append(f"checkpoint_id_missing:{index}")
        elif checkpoint_id in checkpoint_ids:
            errors.append(f"checkpoint_id_duplicate:{index}:{checkpoint_id}")
        checkpoint_ids.add(checkpoint_id)

        status = str(checkpoint.get("status") or "").strip().lower()
        progress_value = checkpoint.get("progress")
        try:
            progress = float(progress_value)
        except (TypeError, ValueError):
            progress = -1.0

        if status == "completed":
            if progress != 100:
                errors.append(f"checkpoint_completed_progress_not_100:{index}")
        elif status == "locked":
            if progress != 0:
                errors.append(f"checkpoint_locked_progress_not_0:{index}")
        elif status == "current":
            current_count += 1
            if progress < 20 or progress > 80:
                errors.append(f"checkpoint_current_progress_out_of_range:{index}")
        elif status == "goal":
            pass
        else:
            errors.append(f"checkpoint_status_invalid:{index}:{status}")

    if current_count != 1:
        errors.append(f"checkpoint_current_count:{current_count}")
    if str(checkpoints[-1].get("status") or "").strip().lower() != "goal":
        errors.append("checkpoint_last_must_be_goal")

    checkpoint_titles = [_checkpoint_title(checkpoint) for checkpoint in checkpoints]
    errors.extend(_validate_titles(checkpoint_titles, "checkpoint"))

    return errors


def _prepare_roadmap_output(output: dict[str, Any], *, domain: str, style_seed: str) -> dict[str, Any]:
    roadmap = output.setdefault("Roadmap_insert", {})
    if not isinstance(roadmap, dict):
        roadmap = {}
        output["Roadmap_insert"] = roadmap
    roadmap_json = _as_dict(roadmap.get("Roadmap_json"))
    roadmap["Roadmap_json"] = roadmap_json
    roadmap_json["domain"] = domain
    roadmap_json["style_seed"] = style_seed
    roadmap["Route_logic"] = roadmap.get("Route_logic") or "qwen_domain_roadmap"
    roadmap["Status"] = "active"
    roadmap["Version"] = roadmap.get("Version") or 1

    items = output.get("Roadmap_items_insert") if isinstance(output.get("Roadmap_items_insert"), list) else []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        try:
            item["Step_order"] = int(item.get("Step_order") or index)
        except (TypeError, ValueError):
            item["Step_order"] = index
        item["Status"] = "not_started"
        title = _item_title(item)
        topic = str(item.get("Topic_name") or title or item.get("Skill_name") or "").strip()
        if topic and item.get("Topic_name") in (None, ""):
            item["Topic_name"] = topic
        if item.get("Skill_name") in (None, "") and (topic or title):
            item["Skill_name"] = topic or title

        source_type = str(item.get("Source_type") or "").strip().lower()
        if index == len(items):
            source_type = "project"
        elif source_type not in ROADMAP_SOURCE_TYPES or source_type == "project":
            source_type = "practice"
        item["Source_type"] = source_type

        completion_type = str(item.get("Completion_check_type") or "").strip().lower()
        if completion_type not in ROADMAP_COMPLETION_TYPES:
            completion_type = "project" if source_type == "project" else "practice"
        item["Completion_check_type"] = completion_type
        if item.get("Description") in (None, ""):
            item["Description"] = f"Разобрать и применить: {topic or title}."
        item["Resources"] = item.get("Resources") or ""
        if item.get("Source_name") in (None, ""):
            item["Source_name"] = "Самостоятельная работа"
        if item.get("Is_free") in (None, ""):
            item["Is_free"] = True
        if item.get("Language") in (None, ""):
            item["Language"] = "ru"
        if item.get("Difficulty") in (None, ""):
            item["Difficulty"] = "basic"
        if item.get("Estimated_hours") in (None, ""):
            item["Estimated_hours"] = 2.0 if source_type != "project" else 4.0
        if item.get("Why_this_material") in (None, ""):
            item["Why_this_material"] = "Шаг подобран под цель, уровень и поддерживаемый domain."
        if item.get("Skill_result") in (None, ""):
            item["Skill_result"] = f"Можешь применить тему: {topic or title}."
        if item.get("Career_value") in (None, ""):
            item["Career_value"] = "Закрывает практический навык для выбранной роли."
        if item.get("Practice_task") in (None, ""):
            item["Practice_task"] = f"Сделай небольшой результат по теме: {topic or title}."
        if not isinstance(item.get("Self_check_questions"), list) or not item["Self_check_questions"]:
            item["Self_check_questions"] = [
                f"Что получилось по теме «{topic or title}»?",
                "Как проверить результат на практике?",
            ]
        if not isinstance(item.get("Completion_check_json"), dict):
            item["Completion_check_json"] = {
                "type": completion_type,
                "required": True,
                "acceptance_criteria": [],
            }
        if item.get("Min_seconds_before_complete") in (None, ""):
            item["Min_seconds_before_complete"] = 600
        if item.get("Xp") in (None, ""):
            item["Xp"] = 80 if source_type != "project" else 160
        if item.get("Pending_xp") in (None, ""):
            item["Pending_xp"] = item.get("Xp") or 80
        if item.get("Verified_xp") in (None, ""):
            item["Verified_xp"] = 0
        if not isinstance(item.get("Xp_policy_json"), dict):
            item["Xp_policy_json"] = {"full_xp_requires_check": True}
        if item.get("Fraud_score") in (None, ""):
            item["Fraud_score"] = 0
        if item.get("Streak_multiplier") in (None, ""):
            item["Streak_multiplier"] = 1.0
        item_json = item.get("Item_json") if isinstance(item.get("Item_json"), dict) else {}
        item_json["domain"] = domain
        item_json["checkpoint_id"] = item_json.get("checkpoint_id") or f"{domain}-{style_seed}-{item['Step_order']}"
        item_json["search_query"] = item_json.get("search_query") or " ".join(
            part for part in (domain, item.get("Skill_name"), title) if part
        )
        item["Item_json"] = item_json

    if not isinstance(roadmap_json.get("checkpoints"), list) or not roadmap_json["checkpoints"]:
        roadmap_json["checkpoints"] = _derive_checkpoints(output, domain=domain)

    output.setdefault("User_profile_update", {})["Dialog_state"] = "roadmap_ready"
    output.setdefault("Motivation_pushes_insert", [])
    return output


def _apply_resource_guard_report(output: dict[str, Any], report: dict[str, Any]) -> None:
    items = output.get("Roadmap_items_insert")
    results = report.get("results") if isinstance(report, dict) else None
    if not isinstance(items, list) or not isinstance(results, list):
        return
    for item, result in zip(items, results):
        if not isinstance(item, dict) or not isinstance(result, dict):
            continue
        item_json = item.get("Item_json") if isinstance(item.get("Item_json"), dict) else {}
        item_json["resource_guard"] = result
        if result.get("decision") != "accepted" and result.get("url"):
            item_json["rejected_resource_url"] = result.get("url")
            item_json.setdefault("search_query", item.get("Resources") or item.get("Name") or "")
            item["Resources"] = ""
        item["Item_json"] = item_json


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
    classifier_output = classify_profile_message(request.user_message)
    followup_update = classify_followup_answer(request.user_message, profile)
    if followup_update:
        classifier_update = classifier_output.setdefault("User_profile_update", {})
        classifier_update.update(followup_update)
        classifier_output.setdefault("signals", {})["followup_answer"] = sorted(followup_update.keys())
    classifier_profile_update = classifier_output.get("User_profile_update") or {}

    topic_guard = guard_profile_topic(profile, classifier_profile_update, request.user_message)
    if not topic_guard["allowed"]:
        unsupported_output = build_unsupported_topic_output(
            request.user_message,
            reason=topic_guard["reason"],
        )
        updated_profile = await update_user_profile(
            session,
            user_id=str(profile["user_id"]),
            update=unsupported_output["User_profile_update"],
        )
        await _insert_llm_run_best_effort(
            session,
            profile_id=str(profile["user_id"]),
            roadmap_id=None,
            prompt_name="profile_analysis",
            input_json={
                "USER_MESSAGE": request.user_message,
                "USER_PROFILE_ROW_JSON": _jsonable(profile),
                "DIALOG_HISTORY": request.dialog_history,
            },
            output_json={
                "classifier_output": classifier_output,
                "unsupported_output": unsupported_output,
                "topic_guard": topic_guard,
            },
            status="failed",
            error_text=f"unsupported_topic:{topic_guard['reason']}",
        )
        return ApiResponse(
            data={
                "classifier_output": classifier_output,
                "llm_output": unsupported_output,
                "unsupported_topic": True,
                "block_reason": topic_guard["reason"],
                "available_areas": unsupported_output["Available_areas"],
                "user_profile": _jsonable(updated_profile),
            }
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
        ollama_fallback_enabled=settings.ollama_fallback_enabled,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_timeout_seconds=settings.ollama_timeout_seconds,
        ollama_num_ctx=settings.ollama_num_ctx,
        ollama_num_predict=settings.ollama_num_predict,
    )
    try:
        llm_output = await llm_client.run_prompt(
            prompt_name="profile_analysis",
            prompt=prompt,
            variables=variables,
        )
    except Exception as exc:
        classifier_profile_update = classifier_output.get("User_profile_update") or {}
        profile_update = dict(classifier_profile_update)
        profile_snapshot = build_profile_snapshot(profile, profile_update)
        backend_decision = get_next_profile_question(profile_snapshot)
        profile_update["Dialog_state"] = (
            "ready_for_roadmap_generation"
            if backend_decision["Ready_for_roadmap_generation"]
            else "collecting_profile"
        )
        fallback_output = {
            "Db_target": "USER_PROFILE",
            "Action": (
                "ready_for_roadmap"
                if backend_decision["Ready_for_roadmap_generation"]
                else "ask_question"
            ),
            "Classifier_output": classifier_output,
            "Backend_decision": backend_decision,
            "User_profile_update": profile_update,
            "Need_question": backend_decision["Need_question"],
            "Next_question": backend_decision["Next_question"],
            "Ready_for_roadmap_generation": backend_decision["Ready_for_roadmap_generation"],
            "Fallback_reason": f"LLM request failed: {exc!r}",
        }
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
            output_json=fallback_output,
            status="failed",
            error_text=repr(exc),
        )
        return ApiResponse(
            data={
                "classifier_output": classifier_output,
                "llm_output": None,
                "fallback_output": fallback_output,
                "llm_status": "failed_classifier_fallback",
                "user_profile": _jsonable(updated_profile),
            }
        )

    llm_profile_update = llm_output.get("User_profile_update") or {}
    llm_topic_guard = guard_profile_topic(profile, llm_profile_update, request.user_message)
    if not llm_topic_guard["allowed"]:
        unsupported_output = build_unsupported_topic_output(
            request.user_message,
            reason=llm_topic_guard["reason"],
        )
        updated_profile = await update_user_profile(
            session,
            user_id=str(profile["user_id"]),
            update=unsupported_output["User_profile_update"],
        )
        await insert_llm_run(
            session,
            profile_id=str(profile["user_id"]),
            roadmap_id=None,
            prompt_name="profile_analysis",
            input_json=variables,
            output_json={
                "classifier_output": classifier_output,
                "llm_output": llm_output,
                "unsupported_output": unsupported_output,
                "topic_guard": llm_topic_guard,
            },
            status="failed",
            error_text=f"unsupported_topic:{llm_topic_guard['reason']}",
        )
        return ApiResponse(
            data={
                "classifier_output": classifier_output,
                "llm_output": unsupported_output,
                "unsupported_topic": True,
                "block_reason": llm_topic_guard["reason"],
                "available_areas": unsupported_output["Available_areas"],
                "user_profile": _jsonable(updated_profile),
            }
        )

    classifier_profile_update = classifier_output.get("User_profile_update") or {}
    profile_update = merge_profile_updates(llm_profile_update, classifier_profile_update)
    profile_snapshot = build_profile_snapshot(profile, profile_update)
    backend_decision = get_next_profile_question(profile_snapshot)

    profile_update["Dialog_state"] = (
        "ready_for_roadmap_generation"
        if backend_decision["Ready_for_roadmap_generation"]
        else "collecting_profile"
    )
    llm_output["Classifier_output"] = classifier_output
    llm_output["Backend_decision"] = backend_decision
    llm_output["User_profile_update"] = profile_update
    llm_output["Need_question"] = backend_decision["Need_question"]
    llm_output["Next_question"] = backend_decision["Next_question"]
    llm_output["Ready_for_roadmap_generation"] = backend_decision["Ready_for_roadmap_generation"]

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
            "classifier_output": classifier_output,
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


@app.post("/api/ai_master", response_model=ApiResponse)
@app.post("/api/ai-master", response_model=ApiResponse)
async def ai_master(
    request: AiMasterRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    settings = _settings()
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="QUESTION is empty")

    profile = await _profile_or_404(session, request.telegram_id)
    profile_id = str(profile["user_id"])

    roadmap = await get_current_roadmap_for_profile(session, profile_id=profile_id)
    items: list[dict[str, Any]] = []
    progress: dict[str, Any] | None = None
    if roadmap:
        roadmap_id = str(roadmap["roadmap_id"])
        items = await get_roadmap_items(session, roadmap_id=roadmap_id)
        progress = await get_roadmap_progress(
            session,
            roadmap_id=roadmap_id,
            profile_id=profile_id,
        )
    else:
        roadmap_id = None

    current_datetime = request.current_datetime or datetime.now(UTC)
    context = build_ai_master_context(
        profile=profile,
        roadmap=roadmap,
        items=items,
        progress=progress,
    )
    variables = {
        "CURRENT_DATETIME": current_datetime.isoformat(),
        "USER_QUESTION": question,
        "AI_MASTER_CONTEXT_JSON": context,
        "DIALOG_HISTORY": request.dialog_history,
    }
    prompt = build_ai_master_prompt(
        question=question,
        context=context,
        dialog_history=request.dialog_history,
        current_datetime=current_datetime,
    )

    llm_client = LlmClient(
        api_llm=settings.api_llm,
        timeout_seconds=settings.llm_timeout_seconds,
        use_local=settings.use_local_llm,
        local_model_name=settings.local_llm_model,
        provider=settings.llm_provider,
        api_base_url=settings.llm_api_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=min(settings.llm_temperature, 0.1),
        json_mode=settings.llm_json_mode,
        ollama_fallback_enabled=settings.ollama_fallback_enabled,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_timeout_seconds=settings.ollama_timeout_seconds,
        ollama_num_ctx=settings.ollama_num_ctx,
        ollama_num_predict=settings.ollama_num_predict,
    )

    try:
        llm_output = await llm_client.run_prompt(
            prompt_name="ai_master",
            prompt=prompt,
            variables=variables,
        )
    except Exception as exc:
        fallback_output = build_ai_master_fallback(
            question=question,
            context=context,
            reason=f"LLM request failed: {exc!r}",
        )
        await _insert_llm_run_best_effort(
            session,
            profile_id=profile_id,
            roadmap_id=roadmap_id,
            prompt_name="ai_master",
            input_json=variables,
            output_json={"fallback_output": fallback_output},
            status="failed",
            error_text=repr(exc),
        )
        return ApiResponse(
            data={
                "answer": fallback_output["answer"],
                "ai_master_output": fallback_output,
                "llm_output": None,
                "llm_status": "failed_guarded_fallback",
                "guard": {
                    "passed": False,
                    "status": "fallback",
                    "errors": ["llm_request_failed"],
                },
                "user_profile": _jsonable(profile),
                "current_roadmap": _jsonable(roadmap),
                "progress": _jsonable(progress),
            }
        )

    guard = validate_ai_master_output(llm_output, context)
    if not guard["passed"]:
        fallback_output = build_ai_master_fallback(
            question=question,
            context=context,
            reason=";".join(guard["errors"]),
        )
        await _insert_llm_run_best_effort(
            session,
            profile_id=profile_id,
            roadmap_id=roadmap_id,
            prompt_name="ai_master",
            input_json=variables,
            output_json={
                "llm_output": llm_output,
                "guard": guard,
                "fallback_output": fallback_output,
            },
            status="failed",
            error_text=";".join(guard["errors"]),
        )
        return ApiResponse(
            data={
                "answer": fallback_output["answer"],
                "ai_master_output": fallback_output,
                "llm_output": llm_output,
                "llm_status": "blocked_guarded_fallback",
                "guard": guard,
                "user_profile": _jsonable(profile),
                "current_roadmap": _jsonable(roadmap),
                "progress": _jsonable(progress),
            }
        )

    await _insert_llm_run_best_effort(
        session,
        profile_id=profile_id,
        roadmap_id=roadmap_id,
        prompt_name="ai_master",
        input_json=variables,
        output_json={"llm_output": llm_output, "guard": guard},
    )
    return ApiResponse(
        data={
            "answer": llm_output["answer"],
            "ai_master_output": llm_output,
            "llm_output": llm_output,
            "llm_status": "ok",
            "guard": guard,
            "user_profile": _jsonable(profile),
            "current_roadmap": _jsonable(roadmap),
            "progress": _jsonable(progress),
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


@app.post("/api/profile/{telegram_id}/roadmap/switch", response_model=ApiResponse)
async def switch_current_roadmap(
    telegram_id: int,
    request: RoadmapSwitchRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await _profile_or_404(session, telegram_id)
    profile_id = str(profile["user_id"])
    roadmap = await update_roadmap_status_for_profile(
        session,
        profile_id=profile_id,
        roadmap_id=request.roadmap_id,
        status="active",
    )
    if not roadmap:
        raise HTTPException(status_code=404, detail="ROADMAP not found for this user")

    items = await get_roadmap_items(session, roadmap_id=str(roadmap["roadmap_id"]))
    progress = await get_roadmap_progress(
        session,
        roadmap_id=str(roadmap["roadmap_id"]),
        profile_id=profile_id,
    )
    roadmaps = await list_roadmaps_for_profile(session, profile_id=profile_id)
    return ApiResponse(
        data={
            "profile": _jsonable(profile),
            "current_roadmap": _jsonable(roadmap),
            "roadmap": _jsonable(roadmap),
            "items": _jsonable(items),
            "roadmap_items": _jsonable(items),
            "progress": _jsonable(progress),
            "roadmaps": _jsonable(roadmaps),
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


@app.post("/api/roadmap/{roadmap_id}/complete", response_model=ApiResponse)
async def complete_roadmap(
    roadmap_id: str,
    request: CompleteRoadmapRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await _profile_or_404(session, request.telegram_id)
    roadmap = await complete_roadmap_for_profile(
        session,
        profile_id=str(profile["user_id"]),
        roadmap_id=roadmap_id,
        allow_skipped=request.allow_skipped,
        force=request.force,
    )
    if not roadmap:
        raise HTTPException(status_code=404, detail="ROADMAP not found for this user")

    blocked = bool(roadmap.pop("_completion_blocked", False))
    completion_stats = roadmap.pop("_completion_stats", {})
    blocking_items = roadmap.pop("_completion_blocking_items", 0)
    if blocked:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "ROADMAP has unfinished items",
                "blocking_items": blocking_items,
                "completion_stats": _jsonable(completion_stats),
            },
        )

    progress = await get_roadmap_progress(
        session,
        roadmap_id=roadmap_id,
        profile_id=str(profile["user_id"]),
    )
    return ApiResponse(
        data={
            "roadmap": _jsonable(roadmap),
            "progress": _jsonable(progress),
            "completion_stats": _jsonable(completion_stats),
        }
    )


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


@app.get("/api/roadmap/item/{item_id}/resources", response_model=ApiResponse)
async def get_item_resources(
    item_id: str,
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await _profile_or_404(session, telegram_id)
    result = await get_roadmap_item_resources(
        session,
        item_id=item_id,
        profile_id=str(profile["user_id"]),
    )
    if not result:
        raise HTTPException(status_code=404, detail="ROADMAP_ITEM not found for this user")
    return ApiResponse(data=_jsonable(result))


@app.patch("/api/roadmap/item/{item_id}/resource", response_model=ApiResponse)
async def patch_item_resource_progress(
    item_id: str,
    request: RoadmapItemResourceProgressRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await _profile_or_404(session, request.telegram_id)
    result = await set_roadmap_item_resource_progress(
        session,
        item_id=item_id,
        profile_id=str(profile["user_id"]),
        resource_id=request.resource_id,
        completed=request.completed,
        current_datetime=request.current_datetime,
    )
    if not result:
        raise HTTPException(status_code=404, detail="ROADMAP_ITEM not found for this user")
    if result.get("not_found"):
        raise HTTPException(
            status_code=404,
            detail={
                "message": "RESOURCE not found",
                "available_resources": _jsonable(result.get("available_resources") or []),
            },
        )
    return ApiResponse(data=_jsonable(result))


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


@app.post("/api/roadmap/item/{item_id}/unskip", response_model=ApiResponse)
async def unskip_item(
    item_id: str,
    request: UnskipRoadmapItemRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    profile = await _profile_or_404(session, request.telegram_id)
    item = await unskip_roadmap_item(
        session,
        item_id=item_id,
        profile_id=str(profile["user_id"]),
        start_now=request.start_now,
        note_text=request.note_text,
    )
    if not item:
        raise HTTPException(status_code=404, detail="ROADMAP_ITEM not found for this user")
    was_unskipped = bool(item.pop("_unskipped", False))
    if not was_unskipped:
        raise HTTPException(status_code=400, detail="ROADMAP_ITEM is not skipped")

    progress = await get_roadmap_progress(
        session,
        roadmap_id=str(item["roadmap_id"]),
        profile_id=str(profile["user_id"]),
    )
    return ApiResponse(
        data={
            "roadmap_item": _jsonable(item),
            "progress": _jsonable(progress),
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

    domain_decision = _roadmap_domain_decision(profile)
    if not domain_decision["supported"]:
        unsupported_output = _build_unsupported_goal_output(
            profile,
            reason="classifier_no_supported_domain",
        )
        await _insert_llm_run_best_effort(
            session,
            profile_id=str(profile["user_id"]),
            roadmap_id=None,
            prompt_name="roadmap_generation",
            input_json={
                "USER_PROFILE_ROW_JSON": _jsonable(profile),
                "DIALOG_HISTORY": request.dialog_history,
                "classifier_output": domain_decision["classifier_output"],
            },
            output_json=unsupported_output,
            status="failed",
            error_text="unsupported_goal:classifier_no_supported_domain",
        )
        return ApiResponse(
            data={
                "generation_status": "unsupported_goal",
                "unsupported_goal": True,
                "classifier_output": domain_decision["classifier_output"],
                "llm_output": unsupported_output,
                "user_profile": _jsonable(profile),
                "created": None,
            }
        )

    domain = str(domain_decision["domain"])
    profile_for_generation = domain_decision["profile_snapshot"]

    profile_decision = get_next_profile_question(profile_for_generation)
    if not profile_decision["Ready_for_roadmap_generation"]:
        raise HTTPException(status_code=400, detail="Profile is not ready for roadmap generation")

    current_datetime = request.current_datetime or datetime.now(UTC)
    style_seed = _roadmap_style_seed(profile_for_generation, current_datetime)
    variables = {
        "CURRENT_DATETIME": current_datetime.isoformat(),
        "USER_PROFILE_ROW_JSON": _jsonable(profile_for_generation),
        "DIALOG_HISTORY": request.dialog_history,
        "SUPPORTED_DOMAIN": domain,
        "STYLE_SEED": style_seed,
        "CLASSIFIER_OUTPUT": domain_decision["classifier_output"],
    }

    llm_client = LlmClient(
        api_llm=settings.api_llm,
        timeout_seconds=settings.llm_timeout_seconds,
        use_local=settings.use_local_llm,
        local_model_name=settings.local_llm_model,
        provider=settings.llm_provider,
        api_base_url=settings.llm_api_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=0.7,
        json_mode=settings.llm_json_mode,
        ollama_fallback_enabled=settings.ollama_fallback_enabled,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_timeout_seconds=settings.ollama_timeout_seconds,
        ollama_num_ctx=settings.ollama_num_ctx,
        ollama_num_predict=settings.ollama_num_predict,
    )

    attempt_errors: list[str] = []
    generation_error: str | None = None
    llm_output: dict[str, Any] | None = None
    for attempt in range(2):
        prompt = _build_roadmap_prompt(
            profile=profile_for_generation,
            domain=domain,
            current_datetime=current_datetime,
            style_seed=style_seed,
            validation_errors=attempt_errors if attempt else None,
        )
        try:
            candidate_output = await llm_client.run_prompt(
                prompt_name="roadmap_generation",
                prompt=prompt,
                variables=variables,
            )
        except Exception as exc:
            attempt_errors = [f"llm_exception:{type(exc).__name__}:{exc!r}"]
            generation_error = ";".join(attempt_errors)
            continue

        candidate_output = _prepare_roadmap_output(
            candidate_output,
            domain=domain,
            style_seed=style_seed,
        )
        validation_errors = _roadmap_output_validation_errors(candidate_output, domain=domain)
        if not validation_errors:
            llm_output = candidate_output
            generation_status = "ok"
            generation_error = None
            break

        attempt_errors = validation_errors
        generation_error = ";".join(validation_errors)
    else:
        llm_output = _prepare_roadmap_output(
            build_template_roadmap(profile_for_generation, now=current_datetime),
            domain=domain,
            style_seed=style_seed,
        )
        llm_output["Invalid_llm_output"] = {
            "errors": attempt_errors,
            "retry_count": 1,
        }
        generation_status = (
            "llm_failed_template_fallback"
            if attempt_errors and attempt_errors[0].startswith("llm_exception:")
            else "llm_invalid_template_fallback"
        )

    resource_guard_report = None
    if settings.resource_guard_enabled and generation_status == "ok":
        original_items = llm_output.get("Roadmap_items_insert") or []
        resource_guard_report = await guard_roadmap_items(
            original_items,
            timeout_seconds=settings.resource_guard_http_timeout_seconds,
            max_html_bytes=settings.resource_guard_max_html_bytes,
        )
        resource_guard_report["status"] = "warnings_only"
        resource_guard_report["reason"] = "roadmap_kept; rejected URLs are stripped from items"
        _apply_resource_guard_report(llm_output, resource_guard_report)
        llm_output["Resource_guard"] = resource_guard_report
    elif settings.resource_guard_enabled:
        resource_guard_report = {
            "classifier": "resource_quality_v1",
            "status": "skipped",
            "reason": generation_status,
            "accepted_count": len(llm_output.get("Roadmap_items_insert") or []),
            "rejected_count": 0,
            "results": [],
        }
        llm_output["Resource_guard"] = resource_guard_report

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
    activated_roadmap = await update_roadmap_status_for_profile(
        session,
        profile_id=str(profile["user_id"]),
        roadmap_id=str(bundle["roadmap"]["roadmap_id"]),
        status="active",
    )
    if activated_roadmap:
        bundle["roadmap"] = activated_roadmap
    await insert_llm_run(
        session,
        profile_id=str(profile["user_id"]),
        roadmap_id=str(bundle["roadmap"]["roadmap_id"]),
        prompt_name="roadmap_generation",
        input_json=variables,
        output_json=llm_output,
        status="failed" if generation_status != "ok" else "success",
        error_text=generation_error,
    )

    return ApiResponse(
        data={
            "generation_status": generation_status,
            "resource_guard": resource_guard_report,
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
        ollama_fallback_enabled=settings.ollama_fallback_enabled,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_timeout_seconds=settings.ollama_timeout_seconds,
        ollama_num_ctx=settings.ollama_num_ctx,
        ollama_num_predict=settings.ollama_num_predict,
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
            error_text=repr(exc),
        )
        return ApiResponse(
            data={
                "saved_feedback": _jsonable(saved_feedback),
                "llm_output": None,
                "updated_roadmap": None,
                "changed_items": [],
                "pushes": [],
                "correction_status": "llm_failed",
                "correction_error": repr(exc),
            }
        )

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
