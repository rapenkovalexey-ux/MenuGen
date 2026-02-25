from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ── MAIN MENU ──────────────────────────────────────────────────────────────────
def main_menu_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="🍽️ Создать меню")
    kb.button(text="👤 Мой профиль")
    kb.button(text="💎 Подписка")
    kb.button(text="💡 Совет дня")
    kb.button(text="📋 Мои меню")
    kb.button(text="🔄 Замена ингредиента")
    kb.button(text="📞 Поддержка")
    kb.button(text="ℹ️ Помощь")
    kb.adjust(2, 2, 2, 2)
    return kb.as_markup(resize_keyboard=True)

# ── DIET TYPES ─────────────────────────────────────────────────────────────────
DIET_BUTTONS = [
    ("🥗 Диетическое",        "diet"),
    ("✅ Правильное питание",  "healthy"),
    ("💪 Усиленное",           "enhanced"),
    ("🌿 Вегетарианское",      "vegetarian"),
    ("🌱 Веганское",           "vegan"),
    ("🥑 Кетогенное",          "keto"),
    ("🫒 Средиземноморское",   "mediterranean"),
    ("🦴 Палео",               "paleo"),
    ("🌾 Безглютеновое",       "glutenfree"),
    ("💊 Диабетическое",       "diabetic"),
    ("💰 Эконом",              "budget"),
    ("🎓 Студенческое",        "student"),
    ("👨‍👩‍👧 Семейное",           "family"),
    ("🏋️ Спортивное",          "sport"),
    ("🍃 Детокс",              "detox"),
]

def diet_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, cb in DIET_BUTTONS:
        builder.button(text=label, callback_data=f"diet:{cb}")
    builder.adjust(2)
    return builder.as_markup()

# ── DAYS SELECTOR ──────────────────────────────────────────────────────────────
def days_keyboard(max_days: int = 31) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    options = [1, 3, 7, 14, 30] if max_days >= 30 else [1, 3] if max_days >= 3 else [1]
    for d in options:
        if d <= max_days:
            builder.button(text=f"{d} {'день' if d==1 else 'дня' if d<5 else 'дней'}", callback_data=f"days:{d}")
    builder.button(text="✏️ Ввести вручную", callback_data="days:custom")
    builder.adjust(3)
    return builder.as_markup()

# ── MEALS CONFIG ───────────────────────────────────────────────────────────────
def meals_keyboard(selected: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    meals = [
        ("🌅 Завтрак", "breakfast"),
        ("🍱 Обед", "lunch"),
        ("🌙 Ужин", "dinner"),
        ("🍎 Перекус", "snack"),
        ("🥤 Второй завтрак", "brunch"),
    ]
    for label, key in meals:
        check = "✅ " if key in selected else ""
        builder.button(text=f"{check}{label}", callback_data=f"meal:{key}")
    builder.button(text="✔️ Готово", callback_data="meal:done")
    builder.adjust(2)
    return builder.as_markup()

# ── PEOPLE COUNT ───────────────────────────────────────────────────────────────
def people_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 7):
        builder.button(text=str(i), callback_data=f"people:{i}")
    builder.button(text="✏️ Другое", callback_data="people:custom")
    builder.adjust(3)
    return builder.as_markup()

# ── CONFIRM / CANCEL ────────────────────────────────────────────────────────────
def confirm_cancel_keyboard(confirm_cb: str, cancel_cb: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=confirm_cb)
    builder.button(text="❌ Отмена", callback_data=cancel_cb)
    builder.adjust(2)
    return builder.as_markup()

# ── MENU ACTIONS ───────────────────────────────────────────────────────────────
def menu_actions_keyboard(menu_id: int, plan: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить блюдо", callback_data=f"edit_menu:{menu_id}")
    builder.button(text="🍴 Рецепты", callback_data=f"recipes:{menu_id}")
    if plan != "free":
        builder.button(text="🛒 Список покупок (PDF)", callback_data=f"shopping:{menu_id}")
        builder.button(text="📄 Меню (PDF)", callback_data=f"menu_pdf:{menu_id}")
    else:
        builder.button(text="🔒 Список покупок [PRO]", callback_data="upgrade")
        builder.button(text="🔒 Меню PDF [PRO]", callback_data="upgrade")
    builder.button(text="🗑️ Удалить", callback_data=f"delete_menu:{menu_id}")
    builder.adjust(2)
    return builder.as_markup()

# ── SUBSCRIPTION ───────────────────────────────────────────────────────────────
def subscription_keyboard(plan: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if plan == "free":
        builder.button(text="🎁 Начать ТРИАЛ (10 дней)", callback_data="sub:trial")
        builder.button(text="💎 Купить PRO — 299₽/мес", callback_data="sub:pay")
    elif plan == "trial":
        builder.button(text="💎 Купить PRO — 299₽/мес", callback_data="sub:pay")
    else:
        builder.button(text="♻️ Продлить подписку", callback_data="sub:pay")
    builder.adjust(1)
    return builder.as_markup()

# ── SUPPORT ────────────────────────────────────────────────────────────────────
def support_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🐛 Сообщить об ошибке", callback_data="support:bug")
    builder.button(text="💡 Предложение", callback_data="support:idea")
    builder.button(text="❓ Вопрос", callback_data="support:question")
    builder.button(text="💳 Вопрос по оплате", callback_data="support:payment")
    builder.adjust(2)
    return builder.as_markup()

# ── SKIP / BACK ────────────────────────────────────────────────────────────────
def skip_keyboard(callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭️ Пропустить", callback_data=callback)
    return builder.as_markup()

def yes_no_keyboard(yes_cb: str, no_cb: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data=yes_cb)
    builder.button(text="❌ Нет", callback_data=no_cb)
    builder.adjust(2)
    return builder.as_markup()
