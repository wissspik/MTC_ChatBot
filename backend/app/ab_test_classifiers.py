from app.classifier import (
    build_profile_snapshot,
    classify_profile_message as rules_classify,
    get_next_profile_question,
)
from app.trained_classifier import classify_profile_message_ml


CASES = [
    {
        "name": "IT clear",
        "text": "Хочу стать Python backend разработчиком, делать API на FastAPI и базы PostgreSQL. Знаю основы Python, готов 5 часов в неделю, люблю практику и статьи.",
        "expected": {"Specific_track": "python_backend", "Current_level": "basic", "Time_per_week_value": 5},
    },
    {
        "name": "IT implicit",
        "text": "Писал маленькие скрипты, теперь хочу делать серверную часть приложений, ручки, авторизацию и хранить данные. Могу заниматься 6 часов, видео не люблю.",
        "expected": {"Specific_track": "python_backend", "Current_level": "basic", "Time_per_week_value": 6},
    },
    {
        "name": "Frontend",
        "text": "Хочу делать интерфейсы сайтов на React и TypeScript, знаю немного HTML CSS, могу 7 часов в неделю.",
        "expected": {"Specific_track": "frontend", "Current_level": "basic", "Time_per_week_value": 7},
    },
    {
        "name": "Design clear",
        "text": "Хочу стать UI/UX дизайнером, умею базово в Figma, хочу практические задания и разбор интерфейсов, 6 часов в неделю.",
        "expected": {"Specific_track": "ui_ux_design", "Current_level": "basic", "Time_per_week_value": 6},
    },
    {
        "name": "Design implicit",
        "text": "Хочу проектировать экраны мобильных приложений, делать прототипы и улучшать пользовательский опыт. В фигме немного разбираюсь.",
        "expected": {"Specific_track": "ui_ux_design", "Current_level": "basic"},
    },
    {
        "name": "Marketing clear",
        "text": "Хочу изучить SMM и digital marketing для малого бизнеса, я новичок, 4 часа в неделю, нужны шаблоны и практика.",
        "expected": {"Specific_track": "smm", "Current_level": "beginner", "Time_per_week_value": 4},
    },
    {
        "name": "Marketing implicit",
        "text": "Хочу продвигать кофейню в соцсетях, делать контент-план, посты, рекламные гипотезы и смотреть метрики.",
        "expected": {"Specific_track": "smm"},
    },
    {
        "name": "SEO",
        "text": "Хочу научиться SEO, продвигать сайт в поиске, подбирать ключевые слова и смотреть трафик.",
        "expected": {"Specific_track": "seo"},
    },
]


def _decision(update: dict) -> dict:
    return get_next_profile_question(build_profile_snapshot({}, update))


def _score(update: dict, expected: dict) -> int:
    return sum(1 for key, value in expected.items() if update.get(key) == value)


def _brief(output: dict, expected: dict) -> dict:
    update = output["User_profile_update"]
    decision = _decision(update)
    return {
        "score": f"{_score(update, expected)}/{len(expected)}",
        "ready": decision["Ready_for_roadmap_generation"],
        "next_question": (decision.get("Next_question") or {}).get("Type") if decision.get("Next_question") else None,
        "update": update,
        "signals": output.get("signals"),
    }


def main() -> None:
    rules_total = 0
    trained_total = 0
    max_total = 0
    for case in CASES:
        expected = case["expected"]
        rules = _brief(rules_classify(case["text"]), expected)
        trained = _brief(classify_profile_message_ml(case["text"]), expected)
        rules_total += int(rules["score"].split("/", 1)[0])
        trained_total += int(trained["score"].split("/", 1)[0])
        max_total += len(expected)
        print(f"\nCASE: {case['name']}")
        print(f"EXPECTED: {expected}")
        print(f"RULES: {rules}")
        print(f"TRAINED: {trained}")

    print("\nSUMMARY")
    print(f"RULES_TOTAL: {rules_total}/{max_total}")
    print(f"TRAINED_TOTAL: {trained_total}/{max_total}")


if __name__ == "__main__":
    main()
