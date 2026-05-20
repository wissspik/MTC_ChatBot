from datetime import UTC, datetime, timedelta
from typing import Any


def _profile_value(profile: dict[str, Any], key: str, default: Any = None) -> Any:
    return profile.get(key) if profile.get(key) is not None else default


def _item(
    order: int,
    *,
    skill: str,
    topic: str,
    name: str,
    source_type: str,
    source_name: str,
    resources: str,
    practice: str,
    difficulty: str = "basic",
    hours: float = 1.5,
) -> dict[str, Any]:
    return {
        "Step_order": order,
        "Skill_name": skill,
        "Topic_name": topic,
        "Name": name,
        "Description": f"Разобрать тему: {topic}.",
        "Resources": resources,
        "Source_type": source_type,
        "Source_name": source_name,
        "Is_free": True,
        "Language": "ru",
        "Difficulty": difficulty,
        "Estimated_hours": hours,
        "Why_this_material": "Выбрано шаблонным классификатором по цели, уровню и формату обучения.",
        "Skill_result": f"Понимаешь и можешь применить: {topic}.",
        "Career_value": "Закрывает базовый навык для выбранной роли.",
        "Practice_task": practice,
        "Self_check_questions": [
            f"Что главное в теме «{topic}»?",
            "Как это применить в своём проекте?",
        ],
        "Completion_check_type": "practice",
        "Completion_check_json": {"type": "short_answer", "required": True},
        "Min_seconds_before_complete": 600,
        "Xp": 80,
        "Pending_xp": 80,
        "Verified_xp": 0,
        "Xp_policy_json": {"policy": "template_fallback"},
        "Status": "not_started",
        "Item_json": {
            "source": "classifier_template_fallback",
            "search_query": resources,
        },
    }


def _python_backend_items() -> list[dict[str, Any]]:
    return [
        _item(1, skill="Python", topic="Синтаксис Python", name="Повторить функции, коллекции и модули", source_type="article", source_name="Python Docs", resources="Python Tutorial: https://docs.python.org/3/tutorial/", practice="Напиши 5 функций для обработки списка задач.", difficulty="basic"),
        _item(2, skill="HTTP", topic="HTTP и REST", name="Разобрать методы HTTP и статусы", source_type="article", source_name="MDN", resources="MDN HTTP Overview: https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview", practice="Опиши 5 endpoint-ов для API трекера обучения."),
        _item(3, skill="SQL", topic="SQL SELECT/JOIN", name="Освоить базовые SQL-запросы", source_type="practice", source_name="SQLBolt", resources="SQLBolt lessons: https://sqlbolt.com/", practice="Составь 6 SQL-запросов для таблиц users, roadmaps, items."),
        _item(4, skill="PostgreSQL", topic="Схема БД", name="Спроектировать таблицы под roadmap", source_type="article", source_name="PostgreSQL Docs", resources="PostgreSQL Tutorial: https://www.postgresql.org/docs/current/tutorial.html", practice="Нарисуй схему из 3 таблиц и связи между ними."),
        _item(5, skill="FastAPI", topic="Первое API", name="Создать CRUD на FastAPI", source_type="article", source_name="FastAPI Docs", resources="FastAPI Tutorial: https://fastapi.tiangolo.com/tutorial/", practice="Сделай GET/POST для списка учебных задач."),
        _item(6, skill="Backend", topic="Валидация данных", name="Добавить Pydantic-схемы", source_type="practice", source_name="FastAPI Docs", resources="FastAPI Body docs: https://fastapi.tiangolo.com/tutorial/body/", practice="Добавь request/response схемы и проверь ошибки валидации."),
        _item(7, skill="Docker", topic="Контейнеризация", name="Упаковать backend и Postgres", source_type="article", source_name="Docker Docs", resources="Docker Compose overview: https://docs.docker.com/compose/", practice="Собери docker-compose для API и Postgres."),
        _item(8, skill="Project", topic="Мини-проект API", name="Собрать portfolio-ready проект", source_type="project", source_name="Свой проект", resources="Итоговый проект: API учебного roadmap с FastAPI + PostgreSQL", practice="Сделай README, 5 endpoint-ов и скриншоты запросов.", difficulty="intermediate", hours=3),
    ]


def _ui_ux_items() -> list[dict[str, Any]]:
    return [
        _item(1, skill="UX", topic="Цели пользователя", name="Собрать JTBD и сценарии", source_type="article", source_name="Nielsen Norman Group", resources="NN/g UX articles: https://www.nngroup.com/articles/", practice="Опиши 3 сценария для учебного приложения.", difficulty="beginner"),
        _item(2, skill="Research", topic="Интервью и наблюдение", name="Подготовить быстрый UX-research", source_type="article", source_name="NN/g", resources="NN/g user research articles: https://www.nngroup.com/articles/user-research/", practice="Составь 7 вопросов для проверки проблемы."),
        _item(3, skill="Figma", topic="Основы Figma", name="Повторить frames, auto layout, components", source_type="course", source_name="Figma Learn", resources="Figma Learn: https://help.figma.com/hc/en-us/categories/360002042553", practice="Собери карточку профиля и bottom navigation."),
        _item(4, skill="UI", topic="Иерархия и сетка", name="Настроить визуальную структуру экрана", source_type="article", source_name="Material Design", resources="Material Design layout: https://m3.material.io/foundations/layout/overview", practice="Перерисуй экран roadmap с понятной сеткой."),
        _item(5, skill="UI", topic="Цвет и контраст", name="Проверить доступность интерфейса", source_type="article", source_name="WCAG", resources="WCAG contrast guidance: https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html", practice="Проверь 5 цветовых пар на контраст."),
        _item(6, skill="UX", topic="Прототипирование", name="Собрать кликабельный прототип", source_type="practice", source_name="Figma", resources="Figma prototyping docs: https://help.figma.com/hc/en-us/articles/360040314193", practice="Свяжи 3 экрана: профиль, roadmap, AI-ментор."),
        _item(7, skill="Testing", topic="Юзабилити-тест", name="Проверить прототип на пользователе", source_type="practice", source_name="Свой тест", resources="Поисковый запрос: usability test script for mobile app", practice="Проведи 1 тест и выпиши 5 проблем."),
        _item(8, skill="Portfolio", topic="Кейс в портфолио", name="Оформить UX/UI case study", source_type="project", source_name="Свой проект", resources="Итоговый проект: case study учебного mini app", practice="Собери кейс: проблема, процесс, экраны, выводы.", difficulty="intermediate", hours=3),
    ]


def _smm_items() -> list[dict[str, Any]]:
    return [
        _item(1, skill="Marketing", topic="Целевая аудитория", name="Описать сегменты аудитории", source_type="practice", source_name="Свой проект", resources="Поисковый запрос: customer persona template", practice="Составь 2 персоны для малого бизнеса.", difficulty="beginner"),
        _item(2, skill="SMM", topic="Позиционирование", name="Сформулировать оффер и тон бренда", source_type="article", source_name="Google Skillshop", resources="Google Skillshop: https://skillshop.withgoogle.com/", practice="Напиши 3 варианта оффера для одной услуги."),
        _item(3, skill="Content", topic="Контент-план", name="Собрать рубрики на 2 недели", source_type="practice", source_name="Свой шаблон", resources="Поисковый запрос: social media content calendar template", practice="Сделай таблицу: дата, формат, идея, CTA."),
        _item(4, skill="Copywriting", topic="Посты и CTA", name="Написать продающие посты", source_type="article", source_name="Meta Business Learn", resources="Meta Business Learn: https://www.facebook.com/business/learn", practice="Напиши 5 постов: боль, польза, кейс, оффер, отзыв."),
        _item(5, skill="Analytics", topic="Метрики SMM", name="Разобрать ER, CTR, CPL", source_type="article", source_name="Google Analytics Help", resources="Google Analytics Help: https://support.google.com/analytics/", practice="Определи 5 KPI для аккаунта малого бизнеса."),
        _item(6, skill="Ads", topic="Тест гипотез", name="Подготовить 3 рекламные гипотезы", source_type="practice", source_name="Свой проект", resources="Поисковый запрос: marketing experiment template", practice="Сформулируй гипотезу, бюджет, метрику успеха."),
        _item(7, skill="Reporting", topic="Отчётность", name="Собрать простой weekly report", source_type="practice", source_name="Свой шаблон", resources="Поисковый запрос: social media weekly report template", practice="Сделай отчёт: что вышло, цифры, вывод, следующий шаг."),
        _item(8, skill="Project", topic="Мини-кампания", name="Запустить план продвижения", source_type="project", source_name="Свой проект", resources="Итоговый проект: SMM-кампания на 14 дней для малого бизнеса", practice="Собери стратегию, контент-план и отчёт по метрикам.", difficulty="intermediate", hours=3),
    ]


def _generic_items(profile: dict[str, Any]) -> list[dict[str, Any]]:
    goal = _profile_value(profile, "goal_text", "выбранный навык")
    return [
        _item(1, skill="Goal", topic="Уточнение результата", name="Сформулировать конечный результат", source_type="practice", source_name="Свой план", resources=f"Поисковый запрос: {goal} beginner roadmap", practice="Запиши 3 измеримых результата обучения.", difficulty="beginner"),
        _item(2, skill="Basics", topic="База", name="Разобрать базовые понятия", source_type="article", source_name="Открытые материалы", resources=f"Поисковый запрос: {goal} basics free course", practice="Сделай конспект на одну страницу."),
        _item(3, skill="Practice", topic="Практика", name="Выполнить первое упражнение", source_type="practice", source_name="Открытые задания", resources=f"Поисковый запрос: {goal} practice tasks", practice="Сделай маленький результат руками."),
        _item(4, skill="Project", topic="Мини-проект", name="Собрать учебный проект", source_type="project", source_name="Свой проект", resources=f"Итоговый мини-проект по цели: {goal}", practice="Покажи результат другому человеку и собери фидбек."),
    ]


def build_template_roadmap(profile: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    track = str(_profile_value(profile, "specific_track", "")).lower()
    direction = _profile_value(profile, "direction")
    target_role = _profile_value(profile, "target_role")
    level = _profile_value(profile, "current_level", "beginner")
    hours_label = _profile_value(profile, "time_per_week_label", "3-7 часов")

    if track == "python_backend":
        title = "Python Backend: FastAPI + PostgreSQL"
        items = _python_backend_items()
    elif track == "ui_ux_design":
        title = "UI/UX дизайнер: практика, Figma и портфолио"
        items = _ui_ux_items()
    elif track in {"smm", "digital_marketing"}:
        title = "SMM и digital marketing для малого бизнеса"
        items = _smm_items()
    else:
        title = f"Персональный маршрут: {_profile_value(profile, 'goal_text', 'обучение')}"
        items = _generic_items(profile)

    roadmap = {
        "Title": title,
        "Direction": direction,
        "Target_role": target_role,
        "Level": level,
        "Estimated_duration_weeks": max(2, round(len(items) / 2)),
        "Hours_per_week_label": hours_label,
        "Route_logic": "classifier_template_fallback",
        "Status": "active",
        "Version": 1,
        "Roadmap_json": {
            "source": "classifier_template_fallback",
            "specific_track": track,
            "reason": "LLM generation failed or was rate-limited",
        },
    }
    pushes = [
        {
            "Push_type": "return_to_route",
            "Tone": "neutral",
            "Message_text": "Вернись к маршруту и закрой один небольшой шаг.",
            "Button_text": "Открыть roadmap",
            "Button_payload": {"action": "open_roadmap"},
            "Scheduled_at": (now + timedelta(days=1)).isoformat(),
            "Status": "planned",
        },
        {
            "Push_type": "xp_opportunity",
            "Tone": "soft",
            "Message_text": "Сегодня можно быстро набрать XP: выбери один практический шаг.",
            "Button_text": "Выбрать шаг",
            "Button_payload": {"action": "next_item"},
            "Scheduled_at": (now + timedelta(days=2)).isoformat(),
            "Status": "planned",
        },
        {
            "Push_type": "test_required",
            "Tone": "neutral",
            "Message_text": "Пора закрепить прогресс короткой самопроверкой.",
            "Button_text": "Пройти проверку",
            "Button_payload": {"action": "self_check"},
            "Scheduled_at": (now + timedelta(days=4)).isoformat(),
            "Status": "planned",
        },
    ]
    return {
        "User_profile_update": {"Dialog_state": "roadmap_ready"},
        "Roadmap_insert": roadmap,
        "Roadmap_items_insert": items,
        "Motivation_pushes_insert": pushes,
        "Fallback": {
            "type": "classifier_template",
            "reason": "LLM generation failed or was rate-limited",
        },
    }
