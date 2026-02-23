 import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os

# Try to register a Unicode font; fall back to built-in if not available
try:
    font_path = os.path.join(os.path.dirname(__file__), "..", "assets", "DejaVuSans.ttf")
    bold_path = os.path.join(os.path.dirname(__file__), "..", "assets", "DejaVuSans-Bold.ttf")
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont("DejaVu", font_path))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold_path))
        FONT = "DejaVu"
        FONT_BOLD = "DejaVu-Bold"
    else:
        FONT = "Helvetica"
        FONT_BOLD = "Helvetica-Bold"
except Exception:
    FONT = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"


DIET_NAMES = {
    "diet": "Диетическое",
    "healthy": "Правильное питание",
    "enhanced": "Усиленное",
    "vegetarian": "Вегетарианское",
    "vegan": "Веганское",
    "keto": "Кетогенное",
    "mediterranean": "Средиземноморское",
    "paleo": "Палео",
    "glutenfree": "Безглютеновое",
    "diabetic": "Диабетическое",
}


def generate_shopping_pdf(shopping_data: dict, menu_meta: dict) -> bytes:
    """Generate a shopping list PDF and return bytes"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", fontName=FONT_BOLD, fontSize=18,
        alignment=TA_CENTER, spaceAfter=6, textColor=colors.HexColor("#2E7D32")
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", fontName=FONT, fontSize=11,
        alignment=TA_CENTER, spaceAfter=12, textColor=colors.HexColor("#555555")
    )
    category_style = ParagraphStyle(
        "Category", fontName=FONT_BOLD, fontSize=13,
        spaceBefore=14, spaceAfter=4, textColor=colors.HexColor("#1565C0")
    )
    item_style = ParagraphStyle(
        "Item", fontName=FONT, fontSize=10,
        spaceBefore=2, spaceAfter=2, leftIndent=10
    )
    footer_style = ParagraphStyle(
        "Footer", fontName=FONT, fontSize=8,
        alignment=TA_CENTER, textColor=colors.grey
    )

    story = []

    # Header
    story.append(Paragraph("🛒 Список покупок", title_style))
    diet_name = DIET_NAMES.get(menu_meta.get("diet_type", ""), menu_meta.get("diet_type", ""))
    story.append(Paragraph(
        f"Режим: {diet_name} | Дней: {menu_meta.get('num_days', '?')} | "
        f"Человек: {menu_meta.get('num_people', '?')}",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#2E7D32")))
    story.append(Spacer(1, 0.3*cm))

    # Categories
    for category in shopping_data.get("categories", []):
        items = category.get("items", [])
        if not items:
            continue

        story.append(Paragraph(f"📦 {category['name']}", category_style))

        table_data = [["Продукт", "Количество", "✓"]]
        for item in items:
            unit = item.get("unit", "")
            amount = item.get("total_amount", "")
            table_data.append([
                item.get("name", ""),
                f"{amount} {unit}",
                "☐"
            ])

        t = Table(
            table_data,
            colWidths=[9*cm, 4*cm, 2*cm],
            hAlign="LEFT"
        )
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F5E9")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1B5E20")),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("FONTNAME", (0, 1), (-1, -1), FONT),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FBF9")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.2*cm))

    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    story.append(Paragraph("Сгенерировано ботом МенюПро | @menu_pro_bot", footer_style))

    doc.build(story)
    return buffer.getvalue()


def generate_menu_pdf(menu_data: dict, menu_meta: dict, plan: str) -> bytes:
    """Generate full menu PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", fontName=FONT_BOLD, fontSize=20,
        alignment=TA_CENTER, spaceAfter=4, textColor=colors.HexColor("#1565C0")
    )
    day_style = ParagraphStyle(
        "Day", fontName=FONT_BOLD, fontSize=14,
        spaceBefore=16, spaceAfter=4, textColor=colors.HexColor("#E65100")
    )
    meal_style = ParagraphStyle(
        "Meal", fontName=FONT_BOLD, fontSize=11,
        spaceBefore=8, spaceAfter=3, textColor=colors.HexColor("#2E7D32")
    )
    dish_style = ParagraphStyle(
        "Dish", fontName=FONT_BOLD, fontSize=10,
        spaceBefore=4, spaceAfter=2
    )
    body_style = ParagraphStyle(
        "Body", fontName=FONT, fontSize=9,
        spaceBefore=1, spaceAfter=1, leftIndent=10
    )
    footer_style = ParagraphStyle(
        "Footer", fontName=FONT, fontSize=8,
        alignment=TA_CENTER, textColor=colors.grey
    )
    diet_name = DIET_NAMES.get(menu_meta.get("diet_type", ""), menu_meta.get("diet_type", ""))

    story = []
    story.append(Paragraph("🍽️ Меню питания", title_style))
    story.append(Paragraph(
        f"{diet_name} | {menu_meta.get('num_days', '?')} дней | {menu_meta.get('num_people', '?')} чел.",
        ParagraphStyle("Sub", fontName=FONT, fontSize=11, alignment=TA_CENTER,
                       spaceAfter=12, textColor=colors.HexColor("#555555"))
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1565C0")))

    for day in menu_data.get("days", []):
        day_num = str(day.get("day", ""))
        day_label = day.get("date_label", "День " + day_num)
        story.append(Paragraph(day_label, day_style))

        if day.get("day_total_calories") and plan != "free":
            story.append(Paragraph(
                "Итого калорий за день: " + str(day["day_total_calories"]) + " ккал",
                body_style
            ))

        for meal in day.get("meals", []):
            meal_name = meal.get("meal_name", meal.get("meal_type", ""))
            meal_time = meal.get("time", "")
            meal_cal = meal.get("total_calories", "")
            if meal_cal and plan != "free":
                cal_str = " | " + str(meal_cal) + " ккал"
            else:
                cal_str = ""
            story.append(Paragraph(meal_name + " (" + meal_time + ")" + cal_str, meal_style))

            for dish in meal.get("dishes", []):
                story.append(Paragraph(dish.get("name", ""), dish_style))
                if dish.get("description"):
                    story.append(Paragraph(dish["description"], body_style))

                # Ingredients table
                ing_data = [["Ингредиент", "Кол-во"]]
                for ing in dish.get("ingredients", []):
                    ing_data.append([
                        ing.get("name", ""),
                        str(ing.get("amount", "")) + " " + str(ing.get("unit", ""))
                    ])
                if len(ing_data) > 1:
                    t = Table(ing_data, colWidths=[9*cm, 4*cm], hAlign="LEFT")
                    t.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E3F2FD")),
                        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                        ("FONTNAME", (0, 1), (-1, -1), FONT),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BBBBBB")),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5FAFF")]),
                    ]))
                    story.append(t)

                # Calories (plan restriction)
                show_cal = not (plan == "free" and meal.get("meal_type") == "dinner")
                if show_cal and dish.get("calories_per_serving") and plan != "free":
                    macros = ""
                    if dish.get("proteins"):
                        macros = (
                            " | Б: " + str(dish["proteins"]) + "г, "
                            "Ж: " + str(dish.get("fats", "?")) + "г, "
                            "У: " + str(dish.get("carbs", "?")) + "г"
                        )
                    story.append(Paragraph(
                        "Калорийность: " + str(dish["calories_per_serving"]) + " ккал" + macros,
                        body_style
                    ))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#DDDDDD")))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Сгенерировано ботом МенюПро | @menu_pro_bot", footer_style))

    doc.build(story)
    return buffer.getvalue()
 
