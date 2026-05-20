import json
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
            "status": roadmap.get("Status") or "active",
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
                "source_type": item.get("Source_type") or "text",
                "source_name": item.get("Source_name"),
                "is_free": item.get("Is_free", True),
                "language": item.get("Language") or "ru",
                "difficulty": item.get("Difficulty"),
                "duration_minutes": item.get("Duration_minutes"),
                "estimated_hours": item.get("Estimated_hours"),
                "why_this_material": item.get("Why_this_material"),
                "skill_result": item.get("Skill_result"),
                "career_value": item.get("Career_value"),
                "practice_task": item.get("Practice_task"),
                "self_check_questions": _json_array(item.get("Self_check_questions") or []),
                "completion_check_type": item.get("Completion_check_type") or "self_check",
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
                "status": item.get("Status") or "not_started",
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
                "push_type": push.get("Push_type") or "return_to_route",
                "tone": push.get("Tone") or "duolingo_aggressive",
                "message_text": push.get("Message_text") or "Вернись к маршруту и закрой один шаг.",
                "button_text": push.get("Button_text"),
                "button_payload": _json(push.get("Button_payload") or {}),
                "scheduled_at": _dt(push.get("Scheduled_at")) or datetime.now(UTC),
                "status": push.get("Status") or "planned",
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
                "push_type": push.get("Push_type") or "return_to_route",
                "tone": push.get("Tone") or "duolingo_aggressive",
                "message_text": push.get("Message_text") or "Маршрут обновлен. Проверь новый шаг.",
                "button_text": push.get("Button_text"),
                "button_payload": _json(push.get("Button_payload") or {}),
                "scheduled_at": _dt(push.get("Scheduled_at")) or datetime.now(UTC),
                "status": push.get("Status") or "planned",
            },
        )
        inserted_pushes.append(dict(push_result.mappings().one()))

    await session.commit()
    return inserted_pushes
