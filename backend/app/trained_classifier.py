import math
import re
from collections import Counter, defaultdict
from typing import Any


def _norm(value: Any) -> str:
    return str(value or "").lower().replace("ё", "е").strip()


def _tokens(text: str) -> list[str]:
    normalized = _norm(text)
    words = re.findall(r"[a-zа-я0-9]+", normalized)
    char_grams: list[str] = []
    compact = re.sub(r"\s+", " ", normalized)
    for size in (3, 4):
        char_grams.extend(f"char:{compact[i:i + size]}" for i in range(max(0, len(compact) - size + 1)))
    return words + char_grams


class NaiveBayesTextClassifier:
    def __init__(self, samples: list[tuple[str, str]]) -> None:
        self.class_doc_counts: Counter[str] = Counter()
        self.class_token_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.class_total_tokens: Counter[str] = Counter()
        self.vocabulary: set[str] = set()
        self.total_docs = 0
        for text, label in samples:
            self.add(text, label)

    def add(self, text: str, label: str) -> None:
        self.total_docs += 1
        self.class_doc_counts[label] += 1
        for token in _tokens(text):
            self.class_token_counts[label][token] += 1
            self.class_total_tokens[label] += 1
            self.vocabulary.add(token)

    def predict(self, text: str) -> dict[str, Any]:
        if not self.total_docs:
            return {"label": None, "confidence": 0.0, "scores": {}}

        token_counts = Counter(_tokens(text))
        vocab_size = max(1, len(self.vocabulary))
        log_scores: dict[str, float] = {}
        for label, doc_count in self.class_doc_counts.items():
            log_prob = math.log(doc_count / self.total_docs)
            total_tokens = self.class_total_tokens[label]
            for token, count in token_counts.items():
                token_prob = (self.class_token_counts[label][token] + 1) / (total_tokens + vocab_size)
                log_prob += count * math.log(token_prob)
            log_scores[label] = log_prob

        max_score = max(log_scores.values())
        exp_scores = {label: math.exp(score - max_score) for label, score in log_scores.items()}
        score_sum = sum(exp_scores.values()) or 1.0
        probs = {label: value / score_sum for label, value in exp_scores.items()}
        label = max(probs, key=probs.get)
        return {"label": label, "confidence": round(probs[label], 4), "scores": probs}


TRACK_SAMPLES = [
    ("python backend fastapi postgresql", "python_backend"),
    ("делать api на python и fastapi", "python_backend"),
    ("серверная часть приложения ручки авторизация база данных", "python_backend"),
    ("backend django postgres redis", "python_backend"),
    ("писал скрипты хочу делать серверную разработку", "python_backend"),
    ("бэкенд бекенд rest api sqlalchemy", "python_backend"),
    ("react frontend javascript typescript", "frontend"),
    ("верстка html css react", "frontend"),
    ("делать интерфейс сайта на vue", "frontend"),
    ("frontend developer spa components", "frontend"),
    ("data science machine learning pandas", "data_science"),
    ("анализ данных python pandas matplotlib", "data_science"),
    ("нейросети машинное обучение", "data_science"),
    ("ui ux figma прототип интерфейс", "ui_ux_design"),
    ("проектировать экраны мобильных приложений", "ui_ux_design"),
    ("пользовательский опыт usability research", "ui_ux_design"),
    ("дизайн приложений вайрфреймы journey map", "ui_ux_design"),
    ("graphic design иллюстрация брендинг", "graphic_design"),
    ("логотип фирменный стиль плакаты", "graphic_design"),
    ("smm соцсети контент план посты", "smm"),
    ("продвигать кофейню в социальных сетях", "smm"),
    ("вести instagram telegram канал бренда", "smm"),
    ("digital marketing воронка реклама аналитика", "digital_marketing"),
    ("таргетированная реклама performance marketing", "digital_marketing"),
    ("seo поисковая оптимизация сайт трафик", "seo"),
    ("ключевые слова выдача поисковик", "seo"),
]


TRACK_MODEL = NaiveBayesTextClassifier(TRACK_SAMPLES)


TRACK_META = {
    "python_backend": {
        "Goal_text": "Python backend разработчик",
        "Direction": "programming",
        "Specific_track": "python_backend",
        "Target_role": "python backend developer",
    },
    "frontend": {
        "Goal_text": "Frontend разработчик",
        "Direction": "programming",
        "Specific_track": "frontend",
        "Target_role": "frontend developer",
    },
    "data_science": {
        "Goal_text": "Data Science специалист",
        "Direction": "programming",
        "Specific_track": "data_science",
        "Target_role": "data science specialist",
    },
    "ui_ux_design": {
        "Goal_text": "UI/UX дизайнер",
        "Direction": "design",
        "Specific_track": "ui_ux_design",
        "Target_role": "ui/ux designer",
    },
    "graphic_design": {
        "Goal_text": "Графический дизайнер",
        "Direction": "design",
        "Specific_track": "graphic_design",
        "Target_role": "graphic designer",
    },
    "smm": {
        "Goal_text": "SMM специалист",
        "Direction": "marketing",
        "Specific_track": "smm",
        "Target_role": "smm specialist",
    },
    "digital_marketing": {
        "Goal_text": "Digital marketing специалист",
        "Direction": "marketing",
        "Specific_track": "digital_marketing",
        "Target_role": "digital marketing specialist",
    },
    "seo": {
        "Goal_text": "SEO специалист",
        "Direction": "marketing",
        "Specific_track": "seo",
        "Target_role": "seo specialist",
    },
}


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
        "format_weights": {"video": 1.0, "article": 1.0, "practice": 1.0},
        "max_video_minutes": None,
        "explanation_style": [],
        "pace_preference": "normal",
    }


def _parse_time(message: str) -> dict[str, Any]:
    text = _norm(message)
    range_match = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s*(час|ч|hour|h)", text)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        value = round((low + high) / 2)
        return {"value": value, "label": _time_label(value), "signal": "hour_range"}

    match = re.search(r"(\d{1,2})\s*(час|часов|часа|ч|hour|hours|h)\w*", text)
    if match:
        value = int(match.group(1))
        return {"value": value, "label": _time_label(value), "signal": "explicit_hours"}

    if any(marker in text for marker in ("мало времени", "до 3", "пару часов", "little time")):
        return {"value": 3, "label": "до 3 часов", "signal": "low_time_words"}
    if any(marker in text for marker in ("много времени", "более 7", "7+", "a lot of time")):
        return {"value": 8, "label": "более 7 часов", "signal": "high_time_words"}
    return {"value": None, "label": None, "signal": None}


def _classify_preferences(message: str) -> dict[str, Any]:
    text = _norm(message)
    labels: set[str] = set()

    keyword_map = {
        "practice": ("практик", "задани", "задач", "проект", "кейс", "practice", "task", "exercise", "template", "шаблон"),
        "article": ("стать", "читать", "текст", "документац", "конспект", "article", "docs", "guide"),
        "video": ("видео", "youtube", "ютуб", "лекци", "video", "lecture"),
        "no_long_video": ("без длинных видео", "не люблю видео", "видео не люблю", "без видео", "without long videos", "no video"),
    }
    for label, markers in keyword_map.items():
        if any(marker in text for marker in markers):
            labels.add(label)

    preference = _default_preference_json()
    formats: list[str] = []
    if "practice" in labels:
        formats.append("practice")
        preference["format_weights"]["practice"] = 1.4
        preference["soft_rules"].append("prefer_practice")
    if "article" in labels:
        formats.append("article")
        preference["format_weights"]["article"] = 1.2
    if "video" in labels and "no_long_video" not in labels:
        formats.append("video")
        preference["format_weights"]["video"] = 1.2
    if "no_long_video" in labels:
        preference["format_weights"]["video"] = 0.2
        preference["max_video_minutes"] = 15
        preference["soft_rules"].append("avoid_long_videos")
    if any(marker in text for marker in ("коротк", "быстр", "short", "quick", "мини")):
        preference["pace_preference"] = "short_steps"
        preference["soft_rules"].append("prefer_short_materials")

    formats = list(dict.fromkeys(formats))
    if formats:
        preference["collected"] = True

    return {
        "formats": formats,
        "preference_json": preference,
        "labels": sorted(labels),
        "extractor_type": "keyword_rules",
    }


def _track_override(message: str) -> str | None:
    text = _norm(message)
    if any(marker in text for marker in ("seo", "поиск", "ключевые слова", "поисков")):
        return "seo"
    if any(marker in text for marker in ("smm", "соцсет", "социальн", "контент-план", "посты", "telegram канал", "instagram")):
        return "smm"
    if any(marker in text for marker in ("react", "typescript", "javascript", "html", "css", "frontend", "фронтенд", "верст")):
        return "frontend"
    if any(marker in text for marker in ("ui/ux", "ux/ui", "figma", "фигм", "прототип", "пользовательский опыт", "экраны мобильных", "интерфейс")):
        return "ui_ux_design"
    if any(marker in text for marker in ("backend", "бэкенд", "бекенд", "fastapi", "django", "postgres", "api", "серверную часть", "серверная часть", "ручки", "авторизац", "база данных", "базы данных")):
        return "python_backend"
    if any(marker in text for marker in ("data science", "машинное обучение", "анализ данных", "pandas", "нейросет")):
        return "data_science"
    if any(marker in text for marker in ("digital marketing", "таргет", "воронк", "performance", "рекламные гипотезы")):
        return "digital_marketing"
    if any(marker in text for marker in ("графический", "брендинг", "логотип", "иллюстрац")):
        return "graphic_design"
    return None


def _broad_goal_update(message: str) -> dict[str, Any]:
    text = _norm(message)
    if any(marker in text for marker in ("программ", "писать код", "it", "разработ", "developer", "код")):
        return {
            "Goal_text": "Изучение программирования",
            "Direction": "programming",
        }
    if any(marker in text for marker in ("дизайн", "интерфейс", "figma", "ux", "ui")):
        return {
            "Goal_text": "Изучение дизайна",
            "Direction": "design",
        }
    if any(marker in text for marker in ("маркетинг", "продвиж", "реклам", "контент", "smm", "seo")):
        return {
            "Goal_text": "Изучение маркетинга",
            "Direction": "marketing",
        }
    if any(marker in text for marker in ("математ", "алгебр", "геометр")):
        return {
            "Goal_text": "Изучение математики",
            "Direction": "math",
        }
    if any(marker in text for marker in ("английск", "english", "язык", "grammar", "speaking")):
        return {
            "Goal_text": "Изучение языка",
            "Direction": "language",
        }
    return {}


def _level_override(message: str) -> str | None:
    text = _norm(message)
    if any(marker in text for marker in ("с нуля", "нович", "ничего не знаю", "никогда не", "только начинаю", "from scratch", "beginner")):
        return "beginner"
    if any(marker in text for marker in ("знаю основы", "основы", "базово", "немного", "чуть", "простые проекты", "маленькие скрипты", "basic")):
        return "basic"
    if any(marker in text for marker in ("работаю", "коммерческий опыт", "middle", "senior", "professional", "для клиентов")):
        return "professional"
    if re.search(r"\b[2-9]\s*(год|года|лет)\b", text):
        return "professional"
    return None


def classify_profile_message_ml(message: str) -> dict[str, Any]:
    track = TRACK_MODEL.predict(message)
    time_info = _parse_time(message)
    preferences = _classify_preferences(message)

    update: dict[str, Any] = {}
    selected_track = _track_override(message) or (track["label"] if track["confidence"] >= 0.65 else None)
    selected_level = _level_override(message)

    if selected_track in TRACK_META:
        update.update(TRACK_META[selected_track])
    else:
        update.update(_broad_goal_update(message))

    if selected_level:
        update["Current_level"] = selected_level

    if time_info["value"] is not None:
        update["Time_per_week_value"] = time_info["value"]
        update["Time_per_week_label"] = time_info["label"]

    if preferences["formats"]:
        update["Preferred_formats"] = preferences["formats"]
        update["Preference_json"] = preferences["preference_json"]

    return {
        "User_profile_update": update,
        "signals": {
            "track": track,
            "level": "keyword_rules" if selected_level else None,
            "time": time_info["signal"],
            "preferences": preferences["labels"],
            "classifier_type": "single_track_naive_bayes",
            "rule_extractors": ["level", "time", "preferences", "broad_goal"],
        },
    }
