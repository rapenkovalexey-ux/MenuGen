import io
import os
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Пути к шрифтам: сначала assets/ рядом с проектом, потом системные
_BASE = os.path.dirname(os.path.abspath(__file__))
_FONT_CANDIDATES = [
    # Шрифты в папке assets/ проекта (работает на Railway)
    (
        os.path.join(_BASE, "..", "assets", "DejaVuSans.ttf"),
        os.path.join(_BASE, "..", "assets", "DejaVuSans-Bold.ttf"),
    ),
    # Системные шрифты (запасной вариант)
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "/usr/local/lib/python3.12/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf",
        "/usr/local/lib/python3.12/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf",
    ),
]

FONT      = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

for _regular, _bold in _FONT_CANDIDATES:
    _regular = os.path.normpath(_regular)
    _bold    = os.path.normpath(_bold)
    if os.path.exists(_regular) and os.path.exists(_bold):
        try:
            pdfmetrics.registerFont(TTFont("DejaVu",      _regular))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", _bold))
            FONT      = "DejaVu"
            FONT_BOLD = "DejaVu-Bold"
        except Exception:
            pass
        break


def _clean(text: str) -> str:
    """Убираем эмодзи — без специального шрифта они дают квадратики."""
    return re.sub(
        r'[\U00010000-\U0010FFFF\U0001F000-\U0001FFFF\u2600-\u27BF\u2300-\u23FF]',
        '', str(text)
    ).strip()


DIET_NAMES = {
    "diet":          "Диетическое",
    "healthy":       "Правильное питание",
    "enhanced":      "Усиленное",
    "vegetarian":    "Вегетарианское",
    "vegan":         "Веганское",
    "keto":          "Кетогенное",
    "mediterranean": "Средиземноморское",
    "paleo":         "Палео",
    "glutenfree":    "Безглютеновое",
    "diabetic":      "Диабетическое",
    "budget":        "Эконом",
    "student":       "Студенческое",
    "family":        "Семейное",
    "sport":         "Спортивное",
    "detox":         "Детокс",
}


# ── Вспомогательная функция стилей ───────────────────────────────────────────

def _style(name, bold=False, size=10, align=TA_LEFT,
           color="#000000", before=0, after=2, indent=0):
    return ParagraphStyle(
        name,
        fontName=FONT_BOLD if bold else FONT,
        fontSize=size,
        alignment=align,
        textColor=colors.HexColor(color),
        spaceBefore=before,
        spaceAfter=after,
        leftIndent=indent,
    )


# ── Список покупок PDF ────────────────────────────────────────────────────────

def generate_shopping_pdf(shopping_data: dict, menu_meta: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm,   bottomMargin=2*cm,
    )

    title_s    = _style("sh_title", bold=True,  size=20, align=TA_CENTER,
                        color="#1B5E20", after=6)
    subtitle_s = _style("sh_sub",   bold=False, size=11, align=TA_CENTER,
                        color="#555555", after=14)
    cat_s      = _style("sh_cat",   bold=True,  size=13,
                        color="#1565C0", before=16, after=5)
    footer_s   = _style("sh_foot",  bold=False, size=8,  align=TA_CENTER,
                        color="#888888")

    story = []
    story.append(Paragraph("Список покупок", title_s))

    diet_name = DIET_NAMES.get(menu_meta.get("diet_type", ""),
                               menu_meta.get("diet_type", ""))
    story.append(Paragraph(
        f"Режим питания: {diet_name}     "
        f"Дней: {menu_meta.get('num_days', '?')}     "
        f"Человек: {menu_meta.get('num_people', '?')}",
        subtitle_s
    ))
    story.append(HRFlowable(width="100%", thickness=2,
                            color=colors.HexColor("#2E7D32")))
    story.append(Spacer(1, 0.4*cm))

    for cat in shopping_data.get("categories", []):
        items = cat.get("items", [])
        if not items:
            continue

        story.append(Paragraph(_clean(cat.get("name", "")), cat_s))

        rows = [["Продукт", "Количество", "V"]]
        for item in items:
            amount = item.get("total_amount", "")
            unit   = item.get("unit", "")
            rows.append([
                _clean(item.get("name", "")),
                f"{amount} {unit}".strip(),
                "[ ]",
            ])

        t = Table(rows, colWidths=[9.5*cm, 4*cm, 2*cm], hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#E8F5E9")),
            ("TEXTCOLOR",     (0,0), (-1,0),  colors.HexColor("#1B5E20")),
            ("FONTNAME",      (0,0), (-1,0),  FONT_BOLD),
            ("FONTNAME",      (0,1), (-1,-1), FONT),
            ("FONTSIZE",      (0,0), (-1,-1), 10),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, colors.HexColor("#F1FBF1")]),
            ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#C8E6C9")),
            ("ALIGN",         (1,0), (2,-1),  "CENTER"),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (0,-1),  8),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3*cm))

    story.append(Spacer(1, 0.6*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#AAAAAA")))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Сгенерировано ботом МенюПро", footer_s))

    doc.build(story)
    return buffer.getvalue()


# ── Меню PDF ──────────────────────────────────────────────────────────────────

def generate_menu_pdf(menu_data: dict, menu_meta: dict, plan: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm,   bottomMargin=2*cm,
    )

    title_s  = _style("m_title", bold=True,  size=20, align=TA_CENTER,
                      color="#1565C0", after=4)
    sub_s    = _style("m_sub",   bold=False, size=11, align=TA_CENTER,
                      color="#555555", after=14)
    day_s    = _style("m_day",   bold=True,  size=15,
                      color="#E65100", before=18, after=5)
    meal_s   = _style("m_meal",  bold=True,  size=11,
                      color="#2E7D32", before=10, after=3)
    dish_s   = _style("m_dish",  bold=True,  size=10, before=5, after=2)
    body_s   = _style("m_body",  bold=False, size=9,
                      before=1, after=1, indent=10)
    footer_s = _style("m_foot",  bold=False, size=8, align=TA_CENTER,
                      color="#888888")

    diet_name = DIET_NAMES.get(menu_meta.get("diet_type", ""),
                               menu_meta.get("diet_type", ""))
    story = []
    story.append(Paragraph("Меню питания", title_s))
    story.append(Paragraph(
        f"{diet_name}     "
        f"{menu_meta.get('num_days', '?')} дней     "
        f"{menu_meta.get('num_people', '?')} чел.",
        sub_s
    ))
    story.append(HRFlowable(width="100%", thickness=2,
                            color=colors.HexColor("#1565C0")))

    for day in menu_data.get("days", []):
        day_label = _clean(day.get("date_label", f"День {day.get('day','')}"))
        story.append(Paragraph(day_label, day_s))

        if day.get("day_total_calories") and plan != "free":
            story.append(Paragraph(
                f"Итого за день: {day['day_total_calories']} ккал", body_s
            ))

        for meal in day.get("meals", []):
            meal_label = _clean(meal.get("meal_name", meal.get("meal_type", "")))
            cal_str = ""
            if meal.get("total_calories") and plan != "free":
                cal_str = f"  —  {meal['total_calories']} ккал"
            story.append(Paragraph(
                f"{meal_label}  ({meal.get('time', '')}){cal_str}", meal_s
            ))

            for dish in meal.get("dishes", []):
                story.append(Paragraph(_clean(dish.get("name", "")), dish_s))
                if dish.get("description"):
                    story.append(Paragraph(_clean(dish["description"]), body_s))

                ing_rows = [["Ингредиент", "Количество"]]
                for ing in dish.get("ingredients", []):
                    ing_rows.append([
                        _clean(ing.get("name", "")),
                        f"{ing.get('amount','')} {ing.get('unit','')}".strip(),
                    ])
                if len(ing_rows) > 1:
                    t = Table(ing_rows, colWidths=[9*cm, 4.5*cm], hAlign="LEFT")
                    t.setStyle(TableStyle([
                        ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#E3F2FD")),
                        ("FONTNAME",      (0,0), (-1,0),  FONT_BOLD),
                        ("FONTNAME",      (0,1), (-1,-1), FONT),
                        ("FONTSIZE",      (0,0), (-1,-1), 8),
                        ("GRID",          (0,0), (-1,-1), 0.3, colors.HexColor("#BBDEFB")),
                        ("TOPPADDING",    (0,0), (-1,-1), 3),
                        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
                        ("ROWBACKGROUNDS",(0,1), (-1,-1),
                         [colors.white, colors.HexColor("#F5FAFF")]),
                        ("LEFTPADDING",   (0,0), (0,-1),  6),
                    ]))
                    story.append(t)

                # Калории (не показываем для ужина на free)
                hide = plan == "free" and meal.get("meal_type") == "dinner"
                if not hide and dish.get("calories_per_serving") and plan != "free":
                    macros = ""
                    if dish.get("proteins"):
                        macros = (
                            f"   Б: {dish['proteins']} г  "
                            f"Ж: {dish.get('fats','?')} г  "
                            f"У: {dish.get('carbs','?')} г"
                        )
                    story.append(Paragraph(
                        f"Калорийность: {dish['calories_per_serving']} ккал{macros}",
                        body_s
                    ))

        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.HexColor("#DDDDDD")))

    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph("Сгенерировано ботом МенюПро", footer_s))
    doc.build(story)
    return buffer.getvalue()
