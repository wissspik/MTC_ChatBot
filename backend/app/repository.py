import json
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _json_array(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def _dt(value: Any) -> Any:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return value


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _norm_text(value: Any) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def _normalize_enum(value: Any, *, allowed: set[str], fallback: str | None, aliases: dict[str, str] | None = None) -> str | None:
    if value is None:
        return fallback

    normalized = _norm_text(value)
    if normalized in allowed:
        return normalized

    aliases = aliases or {}
    for marker, target in aliases.items():
        if marker in normalized:
            return target

    return fallback


def _normalize_current_level(value: Any) -> str | None:
    return _normalize_enum(
        value,
        allowed={"beginner", "basic", "professional"},
        fallback=None,
        aliases={
            "начина": "beginner",
            "нович": "beginner",
            "нулев": "beginner",
            "базов": "basic",
            "основ": "basic",
            "средн": "basic",
            "проф": "professional",
            "продвин": "professional",
            "advanced": "professional",
        },
    )


def _normalize_source_type(value: Any) -> str:
    return _normalize_enum(
        value,
        allowed={"video", "text", "practice", "course", "lecture", "article", "collection", "project"},
        fallback="text",
        aliases={
            "видео": "video",
            "стат": "article",
            "практи": "practice",
            "задач": "practice",
            "курс": "course",
            "лекц": "lecture",
            "подбор": "collection",
            "проект": "project",
        },
    ) or "text"


def _normalize_difficulty(value: Any) -> str | None:
    return _normalize_enum(
        value,
        allowed={"beginner", "basic", "intermediate", "advanced"},
        fallback=None,
        aliases={
            "начина": "beginner",
            "нович": "beginner",
            "базов": "basic",
            "основ": "basic",
            "средн": "intermediate",
            "продвин": "advanced",
            "слож": "advanced",
        },
    )


def _normalize_completion_type(value: Any) -> str:
    return _normalize_enum(
        value,
        allowed={"self_check", "quiz", "practice", "note", "project", "manual"},
        fallback="self_check",
        aliases={
            "самопровер": "self_check",
            "тест": "quiz",
            "quiz": "quiz",
            "практи": "practice",
            "консп": "note",
            "замет": "note",
            "проект": "project",
            "ручн": "manual",
        },
    ) or "self_check"


def _normalize_roadmap_status(value: Any) -> str:
    return _normalize_enum(
        value,
        allowed={"draft", "active", "paused", "completed", "replaced", "archived"},
        fallback="active",
    ) or "active"


def _normalize_item_status(value: Any) -> str:
    return _normalize_enum(
        value,
        allowed={"not_started", "in_progress", "pending_check", "completed", "completed_late", "expired", "skipped", "replaced"},
        fallback="not_started",
    ) or "not_started"


def _normalize_push_type(value: Any) -> str:
    return _normalize_enum(
        value,
        allowed={"deadline_warning", "deadline_expired", "streak_risk", "xp_opportunity", "return_to_route", "test_required"},
        fallback="return_to_route",
        aliases={
            "deadline": "deadline_warning",
            "дедлайн": "deadline_warning",
            "streak": "streak_risk",
            "стрик": "streak_risk",
            "xp": "xp_opportunity",
            "тест": "test_required",
        },
    ) or "return_to_route"


def _normalize_push_tone(value: Any) -> str:
    return _normalize_enum(
        value,
        allowed={"soft", "neutral", "duolingo_aggressive"},
        fallback="duolingo_aggressive",
        aliases={
            "мяг": "soft",
            "нейтр": "neutral",
            "aggressive": "duolingo_aggressive",
            "duolingo": "duolingo_aggressive",
            "дерз": "duolingo_aggressive",
        },
    ) or "duolingo_aggressive"


def _normalize_push_status(value: Any) -> str:
    return _normalize_enum(
        value,
        allowed={"planned", "sent", "cancelled", "failed", "skipped_by_quiet_hours", "rate_limited"},
        fallback="planned",
    ) or "planned"


async def upsert_user_profile(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> dict[str, Any]:
    result = await session.execute(
        text(
            """
            INSERT INTO user_profile (telegram_id, username, first_name, last_name, updated_at)
            VALUES (:telegram_id, :username, :first_name, :last_name, now())
            ON CONFLICT (telegram_id)
            DO UPDATE SET
                username = COALESCE(EXCLUDED.username, user_profile.username),
                first_name = COALESCE(EXCLUDED.first_name, user_profile.first_name),
                last_name = COALESCE(EXCLUDED.last_name, user_profile.last_name),
                updated_at = now()
            RETURNING *
            """
        ),
        {
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
        },
    )
    row = dict(result.mappings().one())
    await session.commit()
    return row


async def get_user_profile(session: AsyncSession, *, telegram_id: int) -> dict[str, Any] | None:
    result = await session.execute(
        text("SELECT * FROM user_profile WHERE telegram_id = :telegram_id"),
        {"telegram_id": telegram_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_roadmap_by_id(
    session: AsyncSession,
    *,
    roadmap_id: str,
) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            "SELECT * FROM roadmap WHERE roadmap_id = :roadmap_id"
        ),
        {"roadmap_id": roadmap_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_roadmap_for_profile(
    session: AsyncSession,
    *,
    profile_id: str,
    roadmap_id: str,
) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            SELECT *
            FROM roadmap
            WHERE roadmap_id = :roadmap_id AND profile_id = :profile_id
            """
        ),
        {"roadmap_id": roadmap_id, "profile_id": profile_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def list_roadmaps_for_profile(
    session: AsyncSession,
    *,
    profile_id: str,
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    status_filter = "AND status = :status" if status is not None else ""
    values: dict[str, Any] = {"profile_id": profile_id, "limit": limit}
    if status is not None:
        values["status"] = status

    result = await session.execute(
        text(
            f"""
            SELECT *
            FROM roadmap
            WHERE profile_id = :profile_id
              {status_filter}
            ORDER BY
                CASE status
                    WHEN 'active' THEN 0
                    WHEN 'paused' THEN 1
                    WHEN 'draft' THEN 2
                    WHEN 'completed' THEN 3
                    ELSE 4
                END,
                updated_at DESC,
                created_at DESC
            LIMIT :limit
            """
        ),
        values,
    )
    return [dict(row) for row in result.mappings().all()]


async def get_current_roadmap_for_profile(
    session: AsyncSession,
    *,
    profile_id: str,
) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            SELECT *
            FROM roadmap
            WHERE profile_id = :profile_id
              AND status IN ('active', 'paused', 'draft')
            ORDER BY
                CASE status
                    WHEN 'active' THEN 0
                    WHEN 'paused' THEN 1
                    WHEN 'draft' THEN 2
                    ELSE 3
                END,
                updated_at DESC,
                created_at DESC
            LIMIT 1
            """
        ),
        {"profile_id": profile_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def update_roadmap_status_for_profile(
    session: AsyncSession,
    *,
    profile_id: str,
    roadmap_id: str,
    status: str,
) -> dict[str, Any] | None:
    if status == "active":
        await session.execute(
            text(
                """
                UPDATE roadmap
                SET status = 'paused',
                    updated_at = now()
                WHERE profile_id = :profile_id
                  AND roadmap_id::TEXT <> :roadmap_id
                  AND status = 'active'
                """
            ),
            {"profile_id": profile_id, "roadmap_id": roadmap_id},
        )

    result = await session.execute(
        text(
            """
            UPDATE roadmap
            SET status = :status,
                updated_at = now()
            WHERE roadmap_id::TEXT = :roadmap_id
              AND profile_id = :profile_id
            RETURNING *
            """
        ),
        {"profile_id": profile_id, "roadmap_id": roadmap_id, "status": status},
    )
    row = result.mappings().first()
    await session.commit()
    return dict(row) if row else None


async def get_roadmap_items(
    session: AsyncSession,
    *,
    roadmap_id: str,
    item_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    if item_ids:
        result = await session.execute(
            text(
                """
                SELECT *
                FROM roadmap_item
                WHERE roadmap_id = :roadmap_id AND item_id::TEXT = ANY(:item_ids)
                ORDER BY step_order
                """
            ),
            {"roadmap_id": roadmap_id, "item_ids": item_ids},
        )
    else:
        result = await session.execute(
            text(
                """
                SELECT *
                FROM roadmap_item
                WHERE roadmap_id = :roadmap_id
                ORDER BY step_order
                LIMIT 40
                """
            ),
            {"roadmap_id": roadmap_id},
        )
    return [dict(row) for row in result.mappings().all()]


async def get_roadmap_item_by_id(
    session: AsyncSession,
    *,
    item_id: str,
    roadmap_id: str | None = None,
) -> dict[str, Any] | None:
    if roadmap_id:
        result = await session.execute(
            text(
                "SELECT * FROM roadmap_item WHERE item_id::TEXT = :item_id AND roadmap_id = :roadmap_id"
            ),
            {"item_id": item_id, "roadmap_id": roadmap_id},
        )
    else:
        result = await session.execute(
            text(
                "SELECT * FROM roadmap_item WHERE item_id::TEXT = :item_id"
            ),
            {"item_id": item_id},
        )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_roadmap_progress(
    session: AsyncSession,
    *,
    roadmap_id: str,
    profile_id: str,
) -> dict[str, Any]:
    result = await session.execute(
        text(
            """
            SELECT
                count(*)::INT AS total_items,
                count(*) FILTER (
                    WHERE status IN ('completed', 'completed_late')
                )::INT AS completed_items,
                count(*) FILTER (WHERE status = 'in_progress')::INT AS in_progress_items,
                count(*) FILTER (WHERE status = 'skipped')::INT AS skipped_items,
                count(*) FILTER (WHERE status = 'not_started')::INT AS not_started_items,
                COALESCE(sum(xp), 0)::INT AS total_xp,
                COALESCE(sum(pending_xp), 0)::INT AS earned_xp
            FROM roadmap_item
            WHERE roadmap_id::TEXT = :roadmap_id
              AND profile_id = :profile_id
            """
        ),
        {"roadmap_id": roadmap_id, "profile_id": profile_id},
    )
    progress = dict(result.mappings().one())
    total = progress["total_items"]
    completed = progress["completed_items"]
    progress["completion_percent"] = round((completed / total) * 100, 2) if total else 0

    current_result = await session.execute(
        text(
            """
            SELECT *
            FROM roadmap_item
            WHERE roadmap_id::TEXT = :roadmap_id
              AND profile_id = :profile_id
              AND status = 'in_progress'
            ORDER BY step_order
            LIMIT 1
            """
        ),
        {"roadmap_id": roadmap_id, "profile_id": profile_id},
    )
    current = current_result.mappings().first()

    next_result = await session.execute(
        text(
            """
            SELECT *
            FROM roadmap_item
            WHERE roadmap_id::TEXT = :roadmap_id
              AND profile_id = :profile_id
              AND status = 'not_started'
            ORDER BY step_order
            LIMIT 1
            """
        ),
        {"roadmap_id": roadmap_id, "profile_id": profile_id},
    )
    next_item = next_result.mappings().first()

    progress["current_item"] = dict(current) if current else None
    progress["next_item"] = dict(next_item) if next_item else None
    return progress


async def start_roadmap_item(
    session: AsyncSession,
    *,
    item_id: str,
    profile_id: str,
) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            UPDATE roadmap_item
            SET status = 'in_progress',
                updated_at = now()
            WHERE item_id::TEXT = :item_id
              AND profile_id = :profile_id
              AND status = 'not_started'
            RETURNING *
            """
        ),
        {"item_id": item_id, "profile_id": profile_id},
    )
    row = result.mappings().first()
    if row:
        await session.commit()
        return dict(row)

    existing = await session.execute(
        text(
            """
            SELECT *
            FROM roadmap_item
            WHERE item_id::TEXT = :item_id
              AND profile_id = :profile_id
            """
        ),
        {"item_id": item_id, "profile_id": profile_id},
    )
    await session.commit()
    existing_row = existing.mappings().first()
    return dict(existing_row) if existing_row else None


async def skip_roadmap_item(
    session: AsyncSession,
    *,
    item_id: str,
    profile_id: str,
    note_text: str | None,
    current_datetime: datetime | None = None,
) -> dict[str, Any] | None:
    now = current_datetime or datetime.now(UTC)
    result = await session.execute(
        text(
            """
            UPDATE roadmap_item
            SET status = 'skipped',
                user_note = COALESCE(:note_text, user_note),
                completed_at = :completed_at,
                updated_at = now()
            WHERE item_id::TEXT = :item_id
              AND profile_id = :profile_id
              AND status NOT IN ('completed', 'completed_late')
            RETURNING *
            """
        ),
        {
            "item_id": item_id,
            "profile_id": profile_id,
            "note_text": note_text,
            "completed_at": now,
        },
    )
    row = result.mappings().first()
    await session.commit()
    return dict(row) if row else None


async def get_roadmap_feedback(
    session: AsyncSession,
    *,
    roadmap_id: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            """
            SELECT *
            FROM roadmap_feedback
            WHERE roadmap_id = :roadmap_id
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"roadmap_id": roadmap_id, "limit": limit},
    )
    return [dict(row) for row in result.mappings().all()]


async def update_user_profile(
    session: AsyncSession,
    *,
    user_id: str,
    update: dict[str, Any],
) -> dict[str, Any]:
    column_map = {
        "username": "username",
        "first_name": "first_name",
        "last_name": "last_name",
        "goal_text": "goal_text",
        "direction": "direction",
        "specific_track": "specific_track",
        "target_role": "target_role",
        "goal_reason": "goal_reason",
        "current_level": "current_level",
        "time_per_week_label": "time_per_week_label",
        "time_per_week_value": "time_per_week_value",
        "preferred_formats": "preferred_formats",
        "wishes": "wishes",
        "preference_json": "preference_json",
        "notification_settings_json": "notification_settings_json",
        "dialog_state": "dialog_state",
        "profile_json": "profile_json",
        "Goal_text": "goal_text",
        "Direction": "direction",
        "Specific_track": "specific_track",
        "Target_role": "target_role",
        "Goal_reason": "goal_reason",
        "Current_level": "current_level",
        "Time_per_week_label": "time_per_week_label",
        "Time_per_week_value": "time_per_week_value",
        "Preferred_formats": "preferred_formats",
        "Wishes": "wishes",
        "Preference_json": "preference_json",
        "Notification_settings_json": "notification_settings_json",
        "Dialog_state": "dialog_state",
        "Profile_json": "profile_json",
    }

    values: dict[str, Any] = {"user_id": user_id}
    assignments: list[str] = []
    for source_key, column in column_map.items():
        if source_key in update and update[source_key] is not None:
            if column in {"preference_json", "notification_settings_json", "profile_json"}:
                assignments.append(f"{column} = CAST(:{column} AS JSONB)")
                values[column] = _json(update[source_key])
            elif column == "current_level":
                level = _normalize_current_level(update[source_key])
                if level is None:
                    continue
                assignments.append(f"{column} = :{column}")
                values[column] = level
            else:
                assignments.append(f"{column} = :{column}")
                values[column] = update[source_key]

    if not assignments:
        profile = await session.execute(
            text("SELECT * FROM user_profile WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        return dict(profile.mappings().one())

    assignments.append("updated_at = now()")
    result = await session.execute(
        text(
            f"""
            UPDATE user_profile
            SET {", ".join(assignments)}
            WHERE user_id = :user_id
            RETURNING *
            """
        ),
        values,
    )
    row = dict(result.mappings().one())
    await session.commit()
    return row


async def insert_roadmap_feedback(
    session: AsyncSession,
    *,
    profile_id: str,
    roadmap_id: str,
    item_ids: list[str],
    feedback_type: str,
    feedback_text: str | None,
) -> list[dict[str, Any]]:
    target_item_ids: list[str | None] = item_ids or [None]
    inserted: list[dict[str, Any]] = []
    for item_id in target_item_ids:
        result = await session.execute(
            text(
                """
                INSERT INTO roadmap_feedback (
                    profile_id, roadmap_id, item_id, feedback_type, feedback_text
                )
                VALUES (
                    :profile_id, :roadmap_id, :item_id, :feedback_type, :feedback_text
                )
                RETURNING *
                """
            ),
            {
                "profile_id": profile_id,
                "roadmap_id": roadmap_id,
                "item_id": item_id,
                "feedback_type": feedback_type,
                "feedback_text": feedback_text,
            },
        )
        inserted.append(dict(result.mappings().one()))
    await session.commit()
    return inserted


async def insert_llm_run(
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
    await session.execute(
        text(
            """
            INSERT INTO llm_run (
                profile_id, roadmap_id, prompt_name, input_json, output_json, status, error_text
            )
            VALUES (
                :profile_id, :roadmap_id, :prompt_name,
                CAST(:input_json AS JSONB), CAST(:output_json AS JSONB),
                :status, :error_text
            )
            """
        ),
        {
            "profile_id": profile_id,
            "roadmap_id": roadmap_id,
            "prompt_name": prompt_name,
            "input_json": _json(input_json),
            "output_json": _json(output_json),
            "status": status,
            "error_text": error_text,
        },
    )
    await session.commit()


async def insert_roadmap_bundle(
    session: AsyncSession,
    *,
    profile_id: str,
    roadmap: dict[str, Any],
    items: list[dict[str, Any]],
    pushes: list[dict[str, Any]],
) -> dict[str, Any]:
    roadmap_result = await session.execute(
        text(
            """
            INSERT INTO roadmap (
                profile_id, title, direction, target_role, level,
                estimated_duration_weeks, hours_per_week_label, route_logic,
                status, version, roadmap_json
            )
            VALUES (
                :profile_id, :title, :direction, :target_role, :level,
                :estimated_duration_weeks, :hours_per_week_label, :route_logic,
                :status, :version, CAST(:roadmap_json AS JSONB)
            )
            RETURNING *
            """
        ),
        {
            "profile_id": profile_id,
            "title": roadmap.get("Title") or "Персональный маршрут",
            "direction": roadmap.get("Direction"),
            "target_role": roadmap.get("Target_role"),
            "level": roadmap.get("Level"),
            "estimated_duration_weeks": roadmap.get("Estimated_duration_weeks"),
            "hours_per_week_label": roadmap.get("Hours_per_week_label"),
            "route_logic": roadmap.get("Route_logic"),
            "status": _normalize_roadmap_status(roadmap.get("Status")),
            "version": roadmap.get("Version") or 1,
            "roadmap_json": _json(roadmap.get("Roadmap_json") or {}),
        },
    )
    roadmap_row = dict(roadmap_result.mappings().one())
    roadmap_id = str(roadmap_row["roadmap_id"])

    inserted_items: list[dict[str, Any]] = []
    for item in items:
        item_result = await session.execute(
            text(
                """
                INSERT INTO roadmap_item (
                    roadmap_id, profile_id, step_order, skill_name, topic_name,
                    name, description, resources, source_type, source_name,
                    is_free, language, difficulty, duration_minutes, estimated_hours,
                    why_this_material, skill_result, career_value, practice_task,
                    self_check_questions, completion_check_type, completion_check_json,
                    min_seconds_before_complete, issued_at, recommended_deadline_at,
                    deadline_at, xp, pending_xp, verified_xp, xp_policy_json,
                    fraud_score, streak_multiplier, status, user_note, completed_at, item_json
                )
                VALUES (
                    :roadmap_id, :profile_id, :step_order, :skill_name, :topic_name,
                    :name, :description, :resources, :source_type, :source_name,
                    :is_free, :language, :difficulty, :duration_minutes, :estimated_hours,
                    :why_this_material, :skill_result, :career_value, :practice_task,
                    CAST(:self_check_questions AS JSONB), :completion_check_type,
                    CAST(:completion_check_json AS JSONB),
                    :min_seconds_before_complete, :issued_at, :recommended_deadline_at,
                    :deadline_at, :xp, :pending_xp, :verified_xp,
                    CAST(:xp_policy_json AS JSONB),
                    :fraud_score, :streak_multiplier, :status, :user_note, :completed_at,
                    CAST(:item_json AS JSONB)
                )
                RETURNING *
                """
            ),
            {
                "roadmap_id": roadmap_id,
                "profile_id": profile_id,
                "step_order": item.get("Step_order"),
                "skill_name": item.get("Skill_name") or "Навык",
                "topic_name": item.get("Topic_name"),
                "name": item.get("Name") or "Шаг маршрута",
                "description": item.get("Description"),
                "resources": item.get("Resources"),
                "source_type": _normalize_source_type(item.get("Source_type")),
                "source_name": item.get("Source_name"),
                "is_free": item.get("Is_free", True),
                "language": item.get("Language") or "ru",
                "difficulty": _normalize_difficulty(item.get("Difficulty")),
                "duration_minutes": item.get("Duration_minutes"),
                "estimated_hours": item.get("Estimated_hours"),
                "why_this_material": item.get("Why_this_material"),
                "skill_result": item.get("Skill_result"),
                "career_value": item.get("Career_value"),
                "practice_task": item.get("Practice_task"),
                "self_check_questions": _json_array(item.get("Self_check_questions") or []),
                "completion_check_type": _normalize_completion_type(item.get("Completion_check_type")),
                "completion_check_json": _json(item.get("Completion_check_json") or {}),
                "min_seconds_before_complete": item.get("Min_seconds_before_complete") or 0,
                "issued_at": _dt(item.get("Issued_at")) or datetime.now(UTC),
                "recommended_deadline_at": _dt(item.get("Recommended_deadline_at")),
                "deadline_at": _dt(item.get("Deadline_at")),
                "xp": item.get("Xp") or 0,
                "pending_xp": item.get("Pending_xp") or 0,
                "verified_xp": item.get("Verified_xp") or 0,
                "xp_policy_json": _json(item.get("Xp_policy_json") or {}),
                "fraud_score": item.get("Fraud_score") or 0,
                "streak_multiplier": item.get("Streak_multiplier") or 1.0,
                "status": _normalize_item_status(item.get("Status")),
                "user_note": item.get("User_note"),
                "completed_at": _dt(item.get("Completed_at")),
                "item_json": _json(item.get("Item_json") or {}),
            },
        )
        inserted_items.append(dict(item_result.mappings().one()))

    inserted_pushes: list[dict[str, Any]] = []
    for push in pushes:
        push_result = await session.execute(
            text(
                """
                INSERT INTO motivation_push (
                    profile_id, roadmap_id, push_type, tone, message_text,
                    button_text, button_payload, scheduled_at, status
                )
                VALUES (
                    :profile_id, :roadmap_id, :push_type, :tone, :message_text,
                    :button_text, CAST(:button_payload AS JSONB), :scheduled_at, :status
                )
                RETURNING *
                """
            ),
            {
                "profile_id": profile_id,
                "roadmap_id": roadmap_id,
                "push_type": _normalize_push_type(push.get("Push_type")),
                "tone": _normalize_push_tone(push.get("Tone")),
                "message_text": push.get("Message_text") or "Вернись к маршруту и закрой один шаг.",
                "button_text": push.get("Button_text"),
                "button_payload": _json(push.get("Button_payload") or {}),
                "scheduled_at": _dt(push.get("Scheduled_at")) or datetime.now(UTC),
                "status": _normalize_push_status(push.get("Status")),
            },
        )
        inserted_pushes.append(dict(push_result.mappings().one()))

    await session.commit()
    return {
        "roadmap": roadmap_row,
        "items": inserted_items,
        "pushes": inserted_pushes,
    }


async def update_roadmap_after_correction(
    session: AsyncSession,
    *,
    roadmap_id: str,
    roadmap_update: dict[str, Any],
) -> dict[str, Any] | None:
    route_logic = roadmap_update.get("Route_logic")
    json_patch = roadmap_update.get("Roadmap_json_patch")

    assignments: list[str] = ["updated_at = now()"]
    values: dict[str, Any] = {"roadmap_id": roadmap_id}

    if route_logic:
        assignments.append("route_logic = :route_logic")
        values["route_logic"] = route_logic

    if json_patch:
        assignments.append("roadmap_json = roadmap_json || CAST(:roadmap_json_patch AS JSONB)")
        values["roadmap_json_patch"] = _json(json_patch)

    if len(assignments) == 1:
        return None

    result = await session.execute(
        text(
            f"""
            UPDATE roadmap
            SET {", ".join(assignments)}
            WHERE roadmap_id = :roadmap_id
            RETURNING *
            """
        ),
        values,
    )
    row = result.mappings().first()
    await session.commit()
    return dict(row) if row else None


async def update_roadmap_items_after_correction(
    session: AsyncSession,
    *,
    roadmap_id: str,
    profile_id: str,
    updates: list[dict[str, Any]],
    max_items: int = 2,
) -> list[dict[str, Any]]:
    column_map = {
        "Step_order": "step_order",
        "Skill_name": "skill_name",
        "Topic_name": "topic_name",
        "Name": "name",
        "Description": "description",
        "Resources": "resources",
        "Source_type": "source_type",
        "Source_name": "source_name",
        "Is_free": "is_free",
        "Language": "language",
        "Difficulty": "difficulty",
        "Duration_minutes": "duration_minutes",
        "Estimated_hours": "estimated_hours",
        "Why_this_material": "why_this_material",
        "Skill_result": "skill_result",
        "Career_value": "career_value",
        "Practice_task": "practice_task",
        "Self_check_questions": "self_check_questions",
        "Completion_check_type": "completion_check_type",
        "Completion_check_json": "completion_check_json",
        "Min_seconds_before_complete": "min_seconds_before_complete",
        "Recommended_deadline_at": "recommended_deadline_at",
        "Deadline_at": "deadline_at",
        "Xp": "xp",
        "Pending_xp": "pending_xp",
        "Verified_xp": "verified_xp",
        "Xp_policy_json": "xp_policy_json",
        "Fraud_score": "fraud_score",
        "Streak_multiplier": "streak_multiplier",
        "Status": "status",
        "User_note": "user_note",
        "Completed_at": "completed_at",
        "Item_json": "item_json",
    }
    json_columns = {
        "self_check_questions",
        "completion_check_json",
        "xp_policy_json",
        "item_json",
    }
    datetime_columns = {"recommended_deadline_at", "deadline_at", "completed_at"}

    changed: list[dict[str, Any]] = []
    for update in updates[:max_items]:
        item_id = update.get("Item_id")
        if not item_id:
            continue

        assignments: list[str] = ["updated_at = now()"]
        values: dict[str, Any] = {
            "item_id": item_id,
            "roadmap_id": roadmap_id,
            "profile_id": profile_id,
        }

        for source_key, column in column_map.items():
            if source_key not in update:
                continue
            value = update[source_key]
            if value is None and source_key not in {"User_note", "Completed_at"}:
                continue

            if column in json_columns:
                assignments.append(f"{column} = CAST(:{column} AS JSONB)")
                if column == "self_check_questions":
                    values[column] = _json_array(value)
                else:
                    values[column] = _json(value)
            elif column in datetime_columns:
                assignments.append(f"{column} = :{column}")
                values[column] = _dt(value)
            elif column == "source_type":
                assignments.append(f"{column} = :{column}")
                values[column] = _normalize_source_type(value)
            elif column == "difficulty":
                assignments.append(f"{column} = :{column}")
                values[column] = _normalize_difficulty(value)
            elif column == "completion_check_type":
                assignments.append(f"{column} = :{column}")
                values[column] = _normalize_completion_type(value)
            elif column == "status":
                assignments.append(f"{column} = :{column}")
                values[column] = _normalize_item_status(value)
            else:
                assignments.append(f"{column} = :{column}")
                values[column] = value

        if len(assignments) == 1:
            continue

        result = await session.execute(
            text(
                f"""
                UPDATE roadmap_item
                SET {", ".join(assignments)}
                WHERE item_id = :item_id
                  AND roadmap_id = :roadmap_id
                  AND profile_id = :profile_id
                RETURNING *
                """
            ),
            values,
        )
        row = result.mappings().first()
        if row:
            changed.append(dict(row))

    await session.commit()
    return changed


async def insert_motivation_pushes(
    session: AsyncSession,
    *,
    profile_id: str,
    roadmap_id: str,
    pushes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    inserted_pushes: list[dict[str, Any]] = []
    for push in pushes:
        push_result = await session.execute(
            text(
                """
                INSERT INTO motivation_push (
                    profile_id, roadmap_id, push_type, tone, message_text,
                    button_text, button_payload, scheduled_at, status
                )
                VALUES (
                    :profile_id, :roadmap_id, :push_type, :tone, :message_text,
                    :button_text, CAST(:button_payload AS JSONB), :scheduled_at, :status
                )
                RETURNING *
                """
            ),
            {
                "profile_id": profile_id,
                "roadmap_id": roadmap_id,
                "push_type": _normalize_push_type(push.get("Push_type")),
                "tone": _normalize_push_tone(push.get("Tone")),
                "message_text": push.get("Message_text") or "Маршрут обновлен. Проверь новый шаг.",
                "button_text": push.get("Button_text"),
                "button_payload": _json(push.get("Button_payload") or {}),
                "scheduled_at": _dt(push.get("Scheduled_at")) or datetime.now(UTC),
                "status": _normalize_push_status(push.get("Status")),
            },
        )
        inserted_pushes.append(dict(push_result.mappings().one()))

    await session.commit()
    return inserted_pushes


async def get_due_motivation_pushes(
    session: AsyncSession,
    *,
    now: datetime,
    limit: int,
    telegram_id: int | None = None,
) -> list[dict[str, Any]]:
    telegram_filter = "AND up.telegram_id = :telegram_id" if telegram_id is not None else ""
    values: dict[str, Any] = {"now": now, "limit": limit}
    if telegram_id is not None:
        values["telegram_id"] = telegram_id

    result = await session.execute(
        text(
            f"""
            SELECT
                mp.*,
                up.telegram_id,
                up.notification_settings_json
            FROM motivation_push mp
            JOIN user_profile up ON up.user_id = mp.profile_id
            WHERE mp.status = 'planned'
              AND mp.scheduled_at <= :now
              {telegram_filter}
            ORDER BY mp.scheduled_at ASC
            LIMIT :limit
            """
        ),
        values,
    )
    return [dict(row) for row in result.mappings().all()]


async def count_sent_pushes_today(
    session: AsyncSession,
    *,
    profile_id: str,
    day_start: datetime,
    day_end: datetime,
) -> int:
    result = await session.execute(
        text(
            """
            SELECT count(*) AS count
            FROM motivation_push
            WHERE profile_id = :profile_id
              AND status = 'sent'
              AND sent_at >= :day_start
              AND sent_at < :day_end
            """
        ),
        {"profile_id": profile_id, "day_start": day_start, "day_end": day_end},
    )
    return int(result.scalar_one())


async def mark_motivation_push_status(
    session: AsyncSession,
    *,
    push_id: str,
    status: str,
    sent_at: datetime | None = None,
) -> dict[str, Any]:
    result = await session.execute(
        text(
            """
            UPDATE motivation_push
            SET status = :status,
                sent_at = :sent_at
            WHERE push_id = :push_id
            RETURNING *
            """
        ),
        {"push_id": push_id, "status": status, "sent_at": sent_at},
    )
    row = dict(result.mappings().one())
    await session.commit()
    return row


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _split_resource_text(value: Any, *, source_type: str = "resource") -> list[dict[str, Any]]:
    text_value = str(value or "").strip()
    if not text_value:
        return []

    raw_parts = re.split(r"\n+|;\s*", text_value)
    parts = [part.strip(" -\t") for part in raw_parts if part.strip(" -\t")]
    resources: list[dict[str, Any]] = []
    for index, part in enumerate(parts or [text_value], start=1):
        url_match = re.search(r"https?://\S+", part)
        url = url_match.group(0) if url_match else None
        title = part.replace(url, "").strip(" :-") if url else part
        resources.append(
            {
                "resource_id": f"resource_{index}",
                "title": title or f"Ресурс {index}",
                "type": source_type,
                "url": url,
            }
        )
    return resources


def _resource_progress_for_item(item: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    item_json = _dict(item.get("item_json") or {})
    existing = _list(item_json.get("resources_progress"))
    if existing:
        resources = existing
    else:
        source_resources = (
            _list(item_json.get("resources"))
            or _list(item_json.get("Resource_list"))
            or _list(item_json.get("resource_list"))
            or _split_resource_text(item.get("resources"), source_type=item.get("source_type") or "resource")
        )
        if not source_resources:
            source_resources = [
                {
                    "resource_id": "resource_1",
                    "title": item.get("name") or "Материал",
                    "type": item.get("source_type") or "resource",
                    "url": None,
                }
            ]
        resources = []
        for index, resource in enumerate(source_resources, start=1):
            if isinstance(resource, dict):
                payload = dict(resource)
            else:
                payload = {"title": str(resource)}
            payload.setdefault("resource_id", f"resource_{index}")
            payload.setdefault("title", payload.get("name") or f"Ресурс {index}")
            payload.setdefault("type", payload.get("source_type") or item.get("source_type") or "resource")
            payload.setdefault("url", payload.get("link"))
            payload.setdefault("completed", False)
            payload.setdefault("completed_at", None)
            resources.append(payload)

    total_xp = int(item.get("xp") or 0)
    default_xp = max(1, round(total_xp / max(1, len(resources)))) if total_xp else 0
    normalized: list[dict[str, Any]] = []
    for index, resource in enumerate(resources, start=1):
        payload = dict(resource) if isinstance(resource, dict) else {"title": str(resource)}
        payload.setdefault("resource_id", f"resource_{index}")
        payload.setdefault("title", payload.get("name") or f"Ресурс {index}")
        payload.setdefault("type", payload.get("source_type") or item.get("source_type") or "resource")
        payload.setdefault("url", payload.get("link"))
        payload["completed"] = bool(payload.get("completed"))
        payload.setdefault("completed_at", None)
        payload["xp"] = int(payload.get("xp") or default_xp)
        normalized.append(payload)

    item_json["resources_progress"] = normalized
    item_json["resource_progress"] = {
        "total": len(normalized),
        "completed": sum(1 for resource in normalized if resource.get("completed")),
    }
    return item_json, normalized


async def get_roadmap_item_resources(
    session: AsyncSession,
    *,
    item_id: str,
    profile_id: str,
) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            SELECT *
            FROM roadmap_item
            WHERE item_id::TEXT = :item_id
              AND profile_id = :profile_id
            """
        ),
        {"item_id": item_id, "profile_id": profile_id},
    )
    row = result.mappings().first()
    if not row:
        return None

    item = dict(row)
    item_json, resources = _resource_progress_for_item(item)
    update_result = await session.execute(
        text(
            """
            UPDATE roadmap_item
            SET item_json = CAST(:item_json AS JSONB),
                updated_at = now()
            WHERE item_id::TEXT = :item_id
              AND profile_id = :profile_id
            RETURNING *
            """
        ),
        {"item_id": item_id, "profile_id": profile_id, "item_json": _json(item_json)},
    )
    await session.commit()
    updated_item = dict(update_result.mappings().one())
    return {"roadmap_item": updated_item, "resources": resources}


async def set_roadmap_item_resource_progress(
    session: AsyncSession,
    *,
    item_id: str,
    profile_id: str,
    resource_id: str,
    completed: bool,
    current_datetime: datetime | None = None,
) -> dict[str, Any] | None:
    now = current_datetime or datetime.now(UTC)
    result = await session.execute(
        text(
            """
            SELECT *
            FROM roadmap_item
            WHERE item_id::TEXT = :item_id
              AND profile_id = :profile_id
            """
        ),
        {"item_id": item_id, "profile_id": profile_id},
    )
    row = result.mappings().first()
    if not row:
        return None

    item = dict(row)
    item_json, resources = _resource_progress_for_item(item)
    target = next((resource for resource in resources if str(resource.get("resource_id")) == resource_id), None)
    if target is None:
        return {"not_found": True, "available_resources": resources}

    was_completed = bool(target.get("completed"))
    xp_value = int(target.get("xp") or 0)
    xp_delta = 0
    completed_courses_delta = 0
    if completed and not was_completed:
        target["completed"] = True
        target["completed_at"] = now.isoformat()
        xp_delta = xp_value
        completed_courses_delta = 1
    elif not completed and was_completed:
        target["completed"] = False
        target["completed_at"] = None
        xp_delta = -xp_value
        completed_courses_delta = -1

    completed_count = sum(1 for resource in resources if resource.get("completed"))
    total_count = len(resources)
    item_json["resources_progress"] = resources
    item_json["resource_progress"] = {
        "total": total_count,
        "completed": completed_count,
    }
    new_status = "completed" if total_count and completed_count == total_count else "in_progress" if completed_count else "not_started"
    pending_xp = sum(int(resource.get("xp") or 0) for resource in resources if resource.get("completed"))
    completed_at = now if new_status == "completed" else None

    update_item_result = await session.execute(
        text(
            """
            UPDATE roadmap_item
            SET item_json = CAST(:item_json AS JSONB),
                status = :status,
                pending_xp = :pending_xp,
                completed_at = :completed_at,
                updated_at = now()
            WHERE item_id::TEXT = :item_id
              AND profile_id = :profile_id
            RETURNING *
            """
        ),
        {
            "item_id": item_id,
            "profile_id": profile_id,
            "item_json": _json(item_json),
            "status": new_status,
            "pending_xp": pending_xp,
            "completed_at": completed_at,
        },
    )

    profile_result = await session.execute(
        text(
            """
            SELECT global_xp, procoins, achievements_json
            FROM user_profile
            WHERE user_id::TEXT = :profile_id
            """
        ),
        {"profile_id": profile_id},
    )
    profile = dict(profile_result.mappings().one())
    achievements = _dict(profile.get("achievements_json") or {})
    achievements.setdefault("completed_courses", 0)
    achievements.setdefault("rewarded_course_milestones", [])
    achievements.setdefault("unlocked", [])

    new_completed_courses = max(0, int(achievements.get("completed_courses") or 0) + completed_courses_delta)
    achievements["completed_courses"] = new_completed_courses

    procoins_delta = 0
    unlocked_now: list[dict[str, Any]] = []
    rewarded_milestones = {int(value) for value in _list(achievements.get("rewarded_course_milestones"))}
    if completed_courses_delta > 0 and new_completed_courses > 0 and new_completed_courses % 3 == 0:
        milestone = new_completed_courses
        if milestone not in rewarded_milestones:
            procoins_delta = 5
            rewarded_milestones.add(milestone)
            achievement = {
                "code": f"every_3_courses_{milestone}",
                "title": f"{milestone} курса пройдено",
                "description": "Награда за каждые 3 завершенных материала",
                "procoins": 5,
                "unlocked_at": now.isoformat(),
            }
            unlocked_now.append(achievement)
            achievements["unlocked"].append(achievement)
    achievements["rewarded_course_milestones"] = sorted(rewarded_milestones)

    update_profile_result = await session.execute(
        text(
            """
            UPDATE user_profile
            SET global_xp = GREATEST(0, global_xp + :xp_delta),
                procoins = GREATEST(0, procoins + :procoins_delta),
                achievements_json = CAST(:achievements_json AS JSONB),
                updated_at = now()
            WHERE user_id::TEXT = :profile_id
            RETURNING *
            """
        ),
        {
            "profile_id": profile_id,
            "xp_delta": xp_delta,
            "procoins_delta": procoins_delta,
            "achievements_json": _json(achievements),
        },
    )

    await session.commit()
    updated_item = dict(update_item_result.mappings().one())
    updated_profile = dict(update_profile_result.mappings().one())
    return {
        "roadmap_item": updated_item,
        "resources": resources,
        "changed_resource": target,
        "resource_progress": item_json["resource_progress"],
        "xp_delta": xp_delta,
        "procoins_delta": procoins_delta,
        "achievements_unlocked": unlocked_now,
        "user_profile": updated_profile,
    }


async def complete_roadmap_item(
    session: AsyncSession,
    *,
    item_id: str,
    profile_id: str,
    spent_seconds: int,
    answers: dict[str, Any] | list[dict[str, Any]] | None,
    note_text: str | None = None,
    practice_result: str | None = None,
    current_datetime: datetime | None = None,
) -> dict[str, Any]:
    """
    Complete a roadmap item without validation checks.
    Returns updated item with XP calculations.
    """
    now = current_datetime or datetime.now(UTC)
    
    # Fetch the item
    result = await session.execute(
        text(
            "SELECT * FROM roadmap_item WHERE item_id::TEXT = :item_id AND profile_id = :profile_id"
        ),
        {"item_id": item_id, "profile_id": profile_id},
    )
    row = result.mappings().first()
    if not row:
        return {}
    
    item = dict(row)
    total_xp = item.get("xp") or 0
    previous_pending_xp = item.get("pending_xp") or 0
    already_completed = item.get("status") in {"completed", "completed_late"}
    pending_xp = total_xp
    xp_delta = 0 if already_completed else max(0, pending_xp - previous_pending_xp)
    user_note = note_text or practice_result
    
    # Update item
    update_result = await session.execute(
        text(
            """
            UPDATE roadmap_item
            SET status = 'completed',
                pending_xp = :pending_xp,
                user_note = COALESCE(:user_note, user_note),
                completed_at = COALESCE(completed_at, :completed_at),
                updated_at = now()
            WHERE item_id::TEXT = :item_id AND profile_id = :profile_id
            RETURNING *
            """
        ),
        {
            "pending_xp": pending_xp,
            "user_note": user_note,
            "completed_at": now,
            "item_id": item_id,
            "profile_id": profile_id,
        },
    )
    
    # Update user profile XP
    profile_result = await session.execute(
        text(
            """
            SELECT global_xp, streak_days FROM user_profile WHERE user_id::TEXT = :profile_id
            """
        ),
        {"profile_id": profile_id},
    )
    profile_row = profile_result.mappings().first()
    if profile_row:
        current_xp = profile_row["global_xp"] or 0
        new_global_xp = current_xp + xp_delta
        
        await session.execute(
            text(
                "UPDATE user_profile SET global_xp = :global_xp, updated_at = now() WHERE user_id::TEXT = :profile_id"
            ),
            {"global_xp": new_global_xp, "profile_id": profile_id},
        )
    
    await session.commit()
    updated_item = dict(update_result.mappings().one())
    return updated_item
