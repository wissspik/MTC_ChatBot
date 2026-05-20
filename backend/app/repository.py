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
