import copy
import re
from typing import Any


def _norm(value: Any) -> str:
    return str(value or "").lower().replace("ё", "е").strip()


def _has(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _merge_json(base: dict[str, Any] | None, update: dict[str, Any] | None) -> dict[str, Any]:
    result = copy.deepcopy(base or {})
    for key, value in (update or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_json(result[key], value)
        else:
            result[key] = value
    return result


def _time_label(hours: int) -> str:
    if hours <= 3:
        return "до 3 часов"
    if hours <= 7:
        return "3-7 часов"
    return "более 7 часов"


def _default_preference_json() -> dict[str, Any]:
    return {
        "collected": False,
        "hard_rules": [],
        "soft_rules": [],
        "blocked_authors": [],
        "blocked_channels": [],
        "blocked_sources": [],
        "preferred_sources": [],
        "format_weights": {
            "video": 1.0,
            "article": 1.0,
            "practice": 1.0,
        },
        "max_video_minutes": None,
        "explanation_style": [],
        "pace_preference": "normal",
    }


def classify_goal(message: str) -> dict[str, Any]:
    text = _norm(message)
    update: dict[str, Any] = {}
    signals: list[str] = []

    if _has(text, "python", "пайтон"):
        update["Direction"] = "programming"
        if _has(text, "backend", "back-end", "бекенд", "бэкенд", "fastapi", "django", "postgres", "api"):
            update["Goal_text"] = "Python backend разработчик"
            update["Specific_track"] = "python_backend"
            update["Target_role"] = "python backend developer"
            signals.append("python_backend")
        elif _has(text, "telegram", "телеграм", "бот"):
            update["Goal_text"] = "Python Telegram bot разработчик"
            update["Specific_track"] = "python_telegram_bots"
            update["Target_role"] = "telegram bot developer"
            signals.append("python_telegram_bots")
        elif _has(text, "data science", "машин", "данн", "аналит"):
            update["Goal_text"] = "Python Data Science специалист"
            update["Specific_track"] = "python_data_science"
            update["Target_role"] = "data science specialist"
            signals.append("python_data_science")
        elif _has(text, "автоматизац", "скрипт", "парсинг"):
            update["Goal_text"] = "Python automation разработчик"
            update["Specific_track"] = "python_automation"
            update["Target_role"] = "automation developer"
            signals.append("python_automation")
        else:
            update["Goal_text"] = "Python разработчик"
            update["Direction"] = "programming"
            signals.append("python_general")

    if _has(text, "frontend", "front-end", "фронтенд", "react", "vue", "javascript", "typescript"):
        update["Goal_text"] = "Frontend разработчик"
        update["Direction"] = "programming"
        update["Specific_track"] = "frontend"
        update["Target_role"] = "frontend developer"
        signals.append("frontend")

    if _has(text, "ui/ux", "ux/ui", "figma", "interface", "интерфейс", "дизайн"):
        update["Goal_text"] = "UI/UX дизайнер"
        update["Direction"] = "design"
        update["Specific_track"] = "ui_ux_design"
        update["Target_role"] = "ui/ux designer"
        signals.append("ui_ux_design")
    elif _has(text, "иллюстрац", "графическ", "брендинг"):
        update["Goal_text"] = "Графический дизайнер"
        update["Direction"] = "design"
        update["Specific_track"] = "graphic_design"
        update["Target_role"] = "graphic designer"
        signals.append("graphic_design")

    if _has(text, "smm", "смм", "social media", "соцсет"):
        update["Goal_text"] = "SMM специалист"
        update["Direction"] = "marketing"
        update["Specific_track"] = "smm"
        update["Target_role"] = "smm specialist"
        signals.append("smm")
    elif _has(text, "marketing", "маркетинг", "таргет", "реклам", "воронк"):
        update["Goal_text"] = "Digital marketing специалист"
        update["Direction"] = "marketing"
        update["Specific_track"] = "digital_marketing"
        update["Target_role"] = "digital marketing specialist"
        signals.append("digital_marketing")

    if _has(text, "математ"):
        update["Goal_text"] = "Изучение математики"
        update["Direction"] = "math"
        update["Specific_track"] = "math"
        update["Target_role"] = "math learner"
        signals.append("math")

    return {"update": update, "signals": signals}


def classify_level(message: str) -> dict[str, Any]:
    text = _norm(message)
    if _has(text, "с нуля", "нович", "beginner", "from scratch", "nothing", "ничего не знаю", "никогда не"):
        return {"value": "beginner", "signal": "beginner_words"}
    if _has(text, "знаю основы", "основы", "basic", "basics", "базов", "немного", "чуть-чуть", "умею figma"):
        return {"value": "basic", "signal": "basic_words"}
    if _has(text, "работаю", "опыт", "experience", "experienced", "middle", "senior", "professional", "профессионал"):
        return {"value": "professional", "signal": "professional_words"}
    if re.search(r"\b[2-9]\s*(год|года|лет)\b", text):
        return {"value": "professional", "signal": "years_experience"}
    return {"value": None, "signal": None}


def classify_time(message: str) -> dict[str, Any]:
    text = _norm(message)
    range_match = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s*(час|ч|hour|h)", text)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        value = round((low + high) / 2)
        return {"value": value, "label": _time_label(value), "signal": "hour_range"}

    match = re.search(r"(\d{1,2})\s*(час|ч|hour|hours|h)\w*", text)
    if match:
        value = int(match.group(1))
        return {"value": value, "label": _time_label(value), "signal": "explicit_hours"}

    if _has(text, "мало времени", "little time", "до 3"):
        return {"value": 3, "label": "до 3 часов", "signal": "low_time_words"}
    if _has(text, "много времени", "a lot of time", "более 7", "7+"):
        return {"value": 8, "label": "более 7 часов", "signal": "high_time_words"}
    return {"value": None, "label": None, "signal": None}


def classify_formats(message: str) -> dict[str, Any]:
    text = _norm(message)
    formats: list[str] = []
    preference = _default_preference_json()
    signals: list[str] = []

    if _has(text, "практик", "задан", "project", "practice", "practical", "task", "exercise", "проект", "делать руками"):
        formats.append("practice")
        preference["format_weights"]["practice"] = 1.4
        preference["soft_rules"].append("prefer_practice")
        signals.append("practice")
    if _has(text, "статья", "статьи", "статей", "article", "articles", "text", "read", "template", "templates", "текст", "читать", "конспект", "шаблон"):
        formats.append("article")
        preference["format_weights"]["article"] = 1.2
        signals.append("article")
    if _has(text, "видео", "video", "videos", "lecture", "лекц"):
        if _has(text, "без длинных видео", "без видео", "не люблю видео", "no long videos", "without long videos", "no video"):
            preference["format_weights"]["video"] = 0.2
            preference["max_video_minutes"] = 15
            preference["soft_rules"].append("avoid_long_videos")
            signals.append("avoid_long_video")
        else:
            formats.append("video")
            preference["format_weights"]["video"] = 1.2
            signals.append("video")
    if _has(text, "коротк", "short", "quick", "быстр", "мини"):
        preference["pace_preference"] = "short_steps"
        preference["soft_rules"].append("prefer_short_materials")
        signals.append("short_steps")

    deduped_formats = list(dict.fromkeys(formats))
    if deduped_formats:
        preference["collected"] = True
    return {"formats": deduped_formats, "preference_json": preference, "signals": signals}


def classify_profile_message(message: str) -> dict[str, Any]:
    goal = classify_goal(message)
    level = classify_level(message)
    time_info = classify_time(message)
    formats = classify_formats(message)

    update: dict[str, Any] = {}
    update.update(goal["update"])

    if level["value"]:
        update["Current_level"] = level["value"]
    if time_info["value"] is not None:
        update["Time_per_week_value"] = time_info["value"]
        update["Time_per_week_label"] = time_info["label"]
    if formats["formats"]:
        update["Preferred_formats"] = formats["formats"]
        update["Preference_json"] = formats["preference_json"]

    return {
        "User_profile_update": update,
        "signals": {
            "goal": goal["signals"],
            "level": level["signal"],
            "time": time_info["signal"],
            "formats": formats["signals"],
        },
    }


def merge_profile_updates(llm_update: dict[str, Any], classifier_update: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(llm_update or {})
    for key, value in (classifier_update or {}).items():
        if value is None:
            continue
        if key == "Preference_json":
            merged[key] = _merge_json(merged.get(key), value)
        else:
            merged[key] = value
    return merged


def classify_followup_answer(message: str, profile: dict[str, Any]) -> dict[str, Any]:
    text = _norm(message)
    update: dict[str, Any] = {}
    direction = profile.get("direction")
    has_track = bool(profile.get("specific_track") or profile.get("target_role"))

    if not has_track:
        if direction == "design":
            if _has(text, "ui/ux", "ux/ui", "ui", "ux", "интерфейс", "приложен", "сайт", "web", "веб", "figma", "фигм"):
                update["Specific_track"] = "ui_ux_design"
                update["Target_role"] = "ui/ux designer"
                update.setdefault("Goal_text", "UI/UX дизайнер")
            elif _has(text, "граф", "логотип", "бренд", "айдентик", "иллюстрац", "плакат"):
                update["Specific_track"] = "graphic_design"
                update["Target_role"] = "graphic designer"
                update.setdefault("Goal_text", "Графический дизайнер")
            elif _has(text, "пока не знаю", "не знаю", "не уверен"):
                update["Specific_track"] = "ui_ux_design"
                update["Target_role"] = "ui/ux designer"
                update.setdefault("Goal_text", "UI/UX дизайнер")

        elif direction == "marketing":
            if _has(text, "smm", "соцсет", "контент", "пост"):
                update["Specific_track"] = "smm"
                update["Target_role"] = "smm specialist"
                update.setdefault("Goal_text", "SMM специалист")
            elif _has(text, "digital", "таргет", "реклам", "воронк", "performance"):
                update["Specific_track"] = "digital_marketing"
                update["Target_role"] = "digital marketing specialist"
                update.setdefault("Goal_text", "Digital marketing специалист")
            elif _has(text, "seo", "поиск", "ключев"):
                update["Specific_track"] = "seo"
                update["Target_role"] = "seo specialist"
                update.setdefault("Goal_text", "SEO специалист")
            elif _has(text, "пока не знаю", "не знаю", "не уверен"):
                update["Specific_track"] = "smm"
                update["Target_role"] = "smm specialist"
                update.setdefault("Goal_text", "SMM специалист")

        elif direction == "programming":
            if _has(text, "backend", "бэкенд", "бекенд", "api", "fastapi", "django"):
                update["Specific_track"] = "python_backend"
                update["Target_role"] = "python backend developer"
                update.setdefault("Goal_text", "Python backend разработчик")
            elif _has(text, "telegram", "телеграм", "бот"):
                update["Specific_track"] = "python_telegram_bots"
                update["Target_role"] = "telegram bot developer"
                update.setdefault("Goal_text", "Python Telegram bot разработчик")
            elif _has(text, "data science", "машин", "данн", "аналит"):
                update["Specific_track"] = "python_data_science"
                update["Target_role"] = "data science specialist"
                update.setdefault("Goal_text", "Python Data Science специалист")
            elif _has(text, "frontend", "фронтенд", "react", "javascript", "typescript"):
                update["Specific_track"] = "frontend"
                update["Target_role"] = "frontend developer"
                update.setdefault("Goal_text", "Frontend разработчик")
            elif _has(text, "пока не знаю", "не знаю", "не уверен"):
                update["Specific_track"] = "programming_general"
                update["Target_role"] = "programming learner"

    if _has(text, "начина", "нович", "с нуля", "beginner"):
        update["Current_level"] = "beginner"
    elif _has(text, "есть база", "базов", "основ", "basic", "немного"):
        update["Current_level"] = "basic"
    elif _has(text, "проф", "работаю", "опыт", "middle", "senior", "professional"):
        update["Current_level"] = "professional"

    if _has(text, "до 3", "до трех", "до трёх", "мало времени"):
        update["Time_per_week_label"] = "до 3 часов"
        update["Time_per_week_value"] = 2
    elif _has(text, "3-7", "3–7", "3 — 7", "3 до 7", "3 часа", "5 часов", "6 часов"):
        update["Time_per_week_label"] = "3-7 часов"
        update["Time_per_week_value"] = 5
    elif _has(text, "более 7", "больше 7", "7+", "много времени"):
        update["Time_per_week_label"] = "более 7 часов"
        update["Time_per_week_value"] = 9

    formats: list[str] = []
    if _has(text, "видео", "video"):
        formats.append("video")
    if _has(text, "практи", "задан", "проект", "practice", "task"):
        formats.append("practice")
    if _has(text, "статья", "статьи", "текст", "читать", "article", "read"):
        formats.append("article")
    if formats:
        update["Preferred_formats"] = list(dict.fromkeys(formats))
        preference = _default_preference_json()
        preference["collected"] = True
        if "video" in formats:
            preference["format_weights"]["video"] = 1.2
        if "practice" in formats:
            preference["format_weights"]["practice"] = 1.4
            preference["soft_rules"].append("prefer_practice")
        if "article" in formats:
            preference["format_weights"]["article"] = 1.2
        update["Preference_json"] = preference

    if _has(text, "backend", "бэкенд", "бекенд", "api", "fastapi", "django"):
        update["Direction"] = "programming"
        update["Specific_track"] = "python_backend"
        update["Target_role"] = "python backend developer"
        update.setdefault("Goal_text", "Python backend разработчик")
    elif _has(text, "telegram", "телеграм", "бот"):
        update["Direction"] = "programming"
        update["Specific_track"] = "python_telegram_bots"
        update["Target_role"] = "telegram bot developer"
        update.setdefault("Goal_text", "Python Telegram bot разработчик")
    elif _has(text, "data science", "машин", "данн", "аналит"):
        update["Direction"] = "programming"
        update["Specific_track"] = "python_data_science"
        update["Target_role"] = "data science specialist"
        update.setdefault("Goal_text", "Python Data Science специалист")
    elif _has(text, "автомат", "скрипт", "парсинг"):
        update["Direction"] = "programming"
        update["Specific_track"] = "python_automation"
        update["Target_role"] = "automation developer"
        update.setdefault("Goal_text", "Python automation разработчик")
    elif _has(text, "frontend", "фронтенд", "react", "javascript", "typescript"):
        update["Direction"] = "programming"
        update["Specific_track"] = "frontend"
        update["Target_role"] = "frontend developer"
        update.setdefault("Goal_text", "Frontend разработчик")
    elif _has(text, "ui/ux", "ux/ui", "figma", "фигм", "интерфейс"):
        update["Direction"] = "design"
        update["Specific_track"] = "ui_ux_design"
        update["Target_role"] = "ui/ux designer"
        update.setdefault("Goal_text", "UI/UX дизайнер")
    elif _has(text, "smm", "соцсет", "контент"):
        update["Direction"] = "marketing"
        update["Specific_track"] = "smm"
        update["Target_role"] = "smm specialist"
        update.setdefault("Goal_text", "SMM специалист")

    if _has(text, "пока не знаю", "не знаю", "не уверен"):
        if profile.get("direction") == "programming" and not profile.get("specific_track"):
            update["Specific_track"] = "programming_general"
            update["Target_role"] = "programming learner"
        elif profile.get("direction") == "design" and not profile.get("specific_track"):
            update["Specific_track"] = "ui_ux_design"
            update["Target_role"] = "ui/ux designer"
        elif profile.get("direction") == "marketing" and not profile.get("specific_track"):
            update["Specific_track"] = "smm"
            update["Target_role"] = "smm specialist"
        elif not profile.get("specific_track"):
            update["Specific_track"] = "general"

    return update


SUPPORTED_LEARNING_AREAS = [
    "Python backend",
    "Telegram-боты на Python",
    "Data Science",
    "Frontend",
    "UI/UX дизайн",
    "Графический дизайн",
    "SMM",
    "Digital marketing",
    "SEO",
]

SUPPORTED_DIRECTIONS = {"programming", "design", "marketing"}

SUPPORTED_SPECIFIC_TRACKS = {
    "python_backend",
    "python_telegram_bots",
    "python_data_science",
    "python_automation",
    "data_science",
    "frontend",
    "ui_ux_design",
    "graphic_design",
    "smm",
    "digital_marketing",
    "seo",
    "programming_general",
}

GOAL_UPDATE_KEYS = {"Goal_text", "Direction", "Specific_track", "Target_role"}
FOLLOWUP_UPDATE_KEYS = {
    "Current_level",
    "Time_per_week_label",
    "Time_per_week_value",
    "Preferred_formats",
    "Preference_json",
    "Wishes",
    "Goal_reason",
}

GOAL_INTENT_MARKERS = (
    "хочу",
    "науч",
    "изуч",
    "осво",
    "стать",
    "обуч",
    "професс",
    "карьер",
    "работать",
    "работу",
    "learn",
    "become",
    "career",
)

SUPPORTED_TOPIC_MARKERS = (
    "python",
    "пайтон",
    "backend",
    "бэкенд",
    "бекенд",
    "frontend",
    "фронтенд",
    "fastapi",
    "django",
    "postgres",
    "api",
    "react",
    "typescript",
    "javascript",
    "html",
    "css",
    "data science",
    "машин",
    "анализ данных",
    "pandas",
    "нейросет",
    "ui/ux",
    "ux/ui",
    "figma",
    "фигм",
    "интерфейс",
    "прототип",
    "дизайн",
    "графическ",
    "брендинг",
    "логотип",
    "иллюстрац",
    "smm",
    "смм",
    "соцсет",
    "контент",
    "digital marketing",
    "маркетинг",
    "таргет",
    "реклам",
    "seo",
    "поиск",
    "ключевые слов",
    "программ",
    "разработ",
    "код",
    "developer",
)

UNSUPPORTED_TOPIC_MARKERS = (
    "осл",
    "кататься",
    "свар",
    "повар",
    "водител",
    "таксист",
    "юрист",
    "адвокат",
    "врач",
    "медиц",
    "стоматолог",
    "электрик",
    "строител",
    "слесар",
    "механик",
    "парикмах",
    "визаж",
)


def _profile_value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _has_goal_update(profile_update: dict[str, Any]) -> bool:
    return any(profile_update.get(key) not in (None, "") for key in GOAL_UPDATE_KEYS)


def _has_only_followup_update(profile_update: dict[str, Any]) -> bool:
    meaningful_keys = {key for key, value in profile_update.items() if value not in (None, "", [], {})}
    return bool(meaningful_keys) and meaningful_keys <= FOLLOWUP_UPDATE_KEYS


def _has_goal_intent(text: str) -> bool:
    return _has(text, *GOAL_INTENT_MARKERS)


def _has_supported_topic_signal(text: str) -> bool:
    return _has(text, *SUPPORTED_TOPIC_MARKERS)


def _has_unsupported_topic_signal(text: str) -> bool:
    return _has(text, *UNSUPPORTED_TOPIC_MARKERS)


def _is_supported_goal_update(profile_update: dict[str, Any]) -> bool:
    specific_track = _profile_value(profile_update, "Specific_track", "specific_track")
    direction = _profile_value(profile_update, "Direction", "direction")
    target_role = _profile_value(profile_update, "Target_role", "target_role")
    goal_text = _profile_value(profile_update, "Goal_text", "goal_text")

    if specific_track:
        return str(specific_track) in SUPPORTED_SPECIFIC_TRACKS
    if direction:
        return str(direction) in SUPPORTED_DIRECTIONS
    if target_role or goal_text:
        text = _norm(f"{goal_text or ''} {target_role or ''}")
        return _has_supported_topic_signal(text) and not _has_unsupported_topic_signal(text)
    return False


def is_supported_profile_goal(profile: dict[str, Any]) -> bool:
    specific_track = _profile_value(profile, "specific_track", "Specific_track")
    direction = _profile_value(profile, "direction", "Direction")
    goal_text = _profile_value(profile, "goal_text", "Goal_text")
    target_role = _profile_value(profile, "target_role", "Target_role")

    if specific_track:
        return str(specific_track) in SUPPORTED_SPECIFIC_TRACKS
    if direction:
        return str(direction) in SUPPORTED_DIRECTIONS
    if goal_text or target_role:
        text = _norm(f"{goal_text or ''} {target_role or ''}")
        return _has_supported_topic_signal(text) and not _has_unsupported_topic_signal(text)
    return False


def guard_profile_topic(
    profile: dict[str, Any],
    profile_update: dict[str, Any],
    message: str | None = None,
) -> dict[str, Any]:
    text = _norm(message)
    has_saved_goal = is_supported_profile_goal(profile)
    has_any_saved_goal = bool(
        _profile_value(profile, "goal_text", "Goal_text")
        or _profile_value(profile, "direction", "Direction")
        or _profile_value(profile, "specific_track", "Specific_track")
        or _profile_value(profile, "target_role", "Target_role")
    )
    has_goal_fields = _has_goal_update(profile_update)
    has_supported_update = _is_supported_goal_update(profile_update) if has_goal_fields else False
    only_followup_update = _has_only_followup_update(profile_update)
    has_goal_intent = _has_goal_intent(text)
    has_supported_message = _has_supported_topic_signal(text)
    has_unsupported_message = _has_unsupported_topic_signal(text)

    if has_any_saved_goal and not has_saved_goal:
        return {"allowed": False, "reason": "saved_goal_unsupported"}

    if has_unsupported_message and has_goal_intent and not has_supported_message:
        return {"allowed": False, "reason": "unsupported_goal_request"}

    if has_goal_fields and not has_supported_update:
        return {"allowed": False, "reason": "unsupported_goal_update"}

    if not has_any_saved_goal and not has_goal_fields:
        return {"allowed": False, "reason": "missing_supported_goal"}

    if has_goal_intent and not has_supported_message and not has_goal_fields and not only_followup_update:
        return {"allowed": False, "reason": "unsupported_goal_intent"}

    return {"allowed": True, "reason": None}


def is_unsupported_initial_topic(
    profile: dict[str, Any],
    profile_update: dict[str, Any],
    message: str | None = None,
) -> bool:
    return not guard_profile_topic(profile, profile_update, message).get("allowed", False)


def build_unsupported_topic_output(message: str, reason: str | None = None) -> dict[str, Any]:
    return {
        "Db_target": "USER_PROFILE",
        "Action": "unsupported_topic",
        "Unsupported_topic": True,
        "Block_reason": reason,
        "Understood_request": message,
        "Answer": (
            "Привет! Пока у нас такой темы нет, мы ее потом добавим. "
            "Сейчас я могу собрать трек только по доступным областям."
        ),
        "Available_areas": SUPPORTED_LEARNING_AREAS,
        "User_profile_update": {"Dialog_state": "start"},
        "Need_question": False,
        "Next_question": None,
        "Ready_for_roadmap_generation": False,
    }


def build_profile_snapshot(profile: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    mapping = {
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
    }
    snapshot = dict(profile)
    for source_key, target_key in mapping.items():
        if source_key in update and update[source_key] is not None:
            snapshot[target_key] = update[source_key]
        elif target_key in update and update[target_key] is not None:
            snapshot[target_key] = update[target_key]
    return snapshot


def get_next_profile_question(profile: dict[str, Any]) -> dict[str, Any]:
    goal_text = profile.get("goal_text")
    direction = profile.get("direction")
    specific_track = profile.get("specific_track")
    target_role = profile.get("target_role")
    current_level = profile.get("current_level")
    time_value = profile.get("time_per_week_value")
    preferred_formats = profile.get("preferred_formats") or []

    if not goal_text:
        return {
            "Need_question": True,
            "Ready_for_roadmap_generation": False,
            "Next_question": {
                "Type": "goal",
                "Text": "Какому навыку ты хочешь научиться?",
                "Buttons": [],
                "Allow_multiple": False,
            },
        }

    if direction == "programming" and specific_track in {None, "", "python"} and goal_text and "Python" in str(goal_text):
        return {
            "Need_question": True,
            "Ready_for_roadmap_generation": False,
            "Next_question": {
                "Type": "specificity",
                "Text": "Какое направление Python тебе ближе?",
                "Buttons": ["Backend", "Telegram-боты", "Data Science", "Автоматизация", "Пока не знаю"],
                "Allow_multiple": False,
            },
        }

    if not specific_track and not target_role:
        if direction == "design":
            buttons = ["UI/UX дизайн", "Графический дизайн", "Пока не знаю"]
            text = "Какое направление дизайна тебе ближе?"
        elif direction == "marketing":
            buttons = ["SMM", "Digital marketing", "SEO", "Пока не знаю"]
            text = "Какое направление маркетинга тебе ближе?"
        elif direction == "programming":
            buttons = ["Backend", "Frontend", "Telegram-боты", "Data Science", "Пока не знаю"]
            text = "Какое направление программирования тебе ближе?"
        else:
            buttons = ["Практика", "Теория", "Профессия", "Пока не знаю"]
            text = "Какое направление внутри этой цели тебе ближе?"
        return {
            "Need_question": True,
            "Ready_for_roadmap_generation": False,
            "Next_question": {
                "Type": "specificity",
                "Text": text,
                "Buttons": buttons,
                "Allow_multiple": False,
            },
        }

    if not current_level:
        return {
            "Need_question": True,
            "Ready_for_roadmap_generation": False,
            "Next_question": {
                "Type": "level",
                "Text": "Как бы ты оценил текущий уровень?",
                "Buttons": ["Начинающий", "Есть базовые знания", "Профессионал"],
                "Allow_multiple": False,
            },
        }

    if time_value is None:
        return {
            "Need_question": True,
            "Ready_for_roadmap_generation": False,
            "Next_question": {
                "Type": "time",
                "Text": "Сколько времени в неделю ты готов уделять обучению?",
                "Buttons": ["До 3 часов", "3-7 часов", "Более 7 часов"],
                "Allow_multiple": False,
            },
        }

    if not preferred_formats:
        return {
            "Need_question": True,
            "Ready_for_roadmap_generation": False,
            "Next_question": {
                "Type": "format",
                "Text": "Какой формат обучения тебе удобнее?",
                "Buttons": ["Видео", "Практические задания", "Статьи"],
                "Allow_multiple": True,
            },
        }

    return {
        "Need_question": False,
        "Ready_for_roadmap_generation": True,
        "Next_question": None,
    }
