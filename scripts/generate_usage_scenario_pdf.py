from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "scenario_usage_bot.pdf"

FONT_REGULAR = r"C:\Windows\Fonts\arial.ttf"
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), style)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont("Arial", FONT_REGULAR))
    pdfmetrics.registerFont(TTFont("Arial-Bold", FONT_BOLD))

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleRu",
        parent=styles["Title"],
        fontName="Arial-Bold",
        fontSize=17,
        leading=20,
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    subtitle = ParagraphStyle(
        "SubtitleRu",
        parent=styles["Normal"],
        fontName="Arial",
        fontSize=9.5,
        leading=12.2,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"),
        spaceAfter=16,
    )
    heading = ParagraphStyle(
        "HeadingRu",
        parent=styles["Heading2"],
        fontName="Arial-Bold",
        fontSize=11.4,
        leading=13,
        spaceBefore=5,
        spaceAfter=3,
        textColor=colors.HexColor("#1f1f1f"),
    )
    body = ParagraphStyle(
        "BodyRu",
        parent=styles["BodyText"],
        fontName="Arial",
        fontSize=9.1,
        leading=11.45,
        alignment=TA_JUSTIFY,
        firstLineIndent=0.55 * cm,
        spaceAfter=6,
    )
    body_no_indent = ParagraphStyle(
        "BodyNoIndentRu",
        parent=body,
        firstLineIndent=0,
        alignment=TA_LEFT,
    )

    story = [
        p("Сценарий использования образовательного Telegram-бота", title),
        p(
            "Бот помогает пользователю сформировать персональный маршрут обучения, "
            "следить за прогрессом и получать поддержку через мини-приложение и AI-мастера.",
            subtitle,
        ),
        p("1. Запуск и первое знакомство", heading),
        p(
            "Пользователь открывает Telegram-бота и нажимает команду /start. Бот приветствует "
            "его, объясняет назначение сервиса и показывает главное меню: «Сделать трек» и "
            "«Информация». В информационном разделе бот сообщает, что помогает подобрать учебные "
            "материалы, построить roadmap под цель, учесть уровень подготовки, время на обучение "
            "и предпочтительный формат занятий.",
            body,
        ),
        p(
            "Основной путь начинается с кнопки «Сделать трек». Пользователь может сразу написать "
            "цель свободным текстом, например: «Хочу стать Python backend-разработчиком». Если в "
            "сообщении уже указаны уровень, время или пожелания, бот сохраняет эти данные в профиль "
            "и не задает повторные вопросы.",
            body,
        ),
        p("2. Сбор профиля пользователя", heading),
        p(
            "Бот по одному задает уточняющие вопросы: направление обучения, текущий уровень, "
            "доступное время в неделю и удобный формат материалов. Для быстрых ответов используются "
            "кнопки: например, «Начинающий», «Есть базовые знания», «Профессионал», «До 3 часов», "
            "«3-7 часов», «Более 7 часов», «Видео», «Статьи», «Практика».",
            body,
        ),
        p(
            "На последнем, необязательном шаге бот спрашивает пожелания и ограничения по материалам. "
            "Пользователь может попросить больше практики, убрать длинные видео, не показывать "
            "конкретный источник или написать свое ограничение. Эти ответы сохраняются в профиле.",
            body,
        ),
        p("3. Создание учебного маршрута", heading),
        p(
            "Когда данных достаточно, бот показывает сообщение ожидания и отправляет профиль на "
            "backend. LLM-модуль формирует roadmap: название маршрута, примерную длительность, "
            "последовательность тем, материалы, практические задания, вопросы самопроверки и правила "
            "начисления XP. Каждый шаг получает описание, сложность и критерий завершения.",
            body,
        ),
        p(
            "После генерации бот отправляет пользователю итог: «Твой план успешно создан», указывает "
            "цель, длительность и основные блоки. Под сообщением доступны действия «Скорректировать» "
            "и «Создать заново», а в меню появляются «Открыть карту», «Профиль» и «AI-мастер».",
            body,
        ),
        p("4. Работа с roadmap в мини-приложении", heading),
        p(
            "В мини-приложении пользователь видит свой маршрут как карту прогресса. В карточке шага "
            "отображаются тема, источник, задание, вопросы самопроверки и статус. Пользователь "
            "изучает материал, выполняет практику, отвечает на проверочный вопрос и отмечает шаг "
            "завершенным. За прохождение начисляются XP, обновляется streak и прогресс по навыкам.",
            body,
        ),
        p(
            "Если материал оказался слишком сложным, слишком легким или уже знакомым, пользователь "
            "отправляет обратную связь. Backend передает текущий roadmap и комментарий в LLM-модуль "
            "коррекции, после чего отдельные шаги можно заменить, упростить или дополнить практикой.",
            body,
        ),
        p("5. Поддержка, профиль и мотивация", heading),
        p(
            "Раздел «Профиль» показывает имя пользователя, уровень, XP, прокоины, streak, цель "
            "обучения и прогресс по ключевым навыкам. Это превращает обучение в понятный цикл: "
            "выбрал шаг, изучил материал, подтвердил результат, получил прогресс.",
            body,
        ),
        p(
            "AI-мастер работает как помощник внутри маршрута. Пользователь может спросить, что делать "
            "на текущем шаге, попросить объяснить тему проще или получить идею для практики. Ответ "
            "строится на профиле, roadmap и текущем прогрессе.",
            body,
        ),
        p(
            "После создания маршрута бот планирует мотивационные уведомления. Они напоминают вернуться "
            "к обучению, пройти мини-тест или закрыть следующий шаг, но учитывают ограничения: лимит "
            "пушей в день, quiet hours и настройки пользователя. Когда маршрут почти завершен, "
            "приложение предлагает создать новый roadmap или продолжить работу с текущим.",
            body,
        ),
        Spacer(1, 8),
        p(
            "Ключевой результат сценария: пользователь за несколько сообщений получает индивидуальный "
            "учебный трек и дальше работает с ним через Telegram и WebApp без ручной сборки плана.",
            body_no_indent,
        ),
    ]

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=1.35 * cm,
        leftMargin=1.35 * cm,
        topMargin=1.25 * cm,
        bottomMargin=1.25 * cm,
        title="Сценарий использования образовательного Telegram-бота",
        author="MTC ChatBot",
    )
    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    main()
