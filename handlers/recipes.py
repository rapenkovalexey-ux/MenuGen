import logging
import urllib.parse
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import AsyncSessionLocal, Menu, get_user_plan
from services.groq_service import suggest_recipe_queries

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("recipes:"))
async def show_recipes(call: CallbackQuery):
    menu_id = int(call.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        plan = await get_user_plan(session, call.from_user.id)
        menu = await session.get(Menu, menu_id)

    if not menu:
        await call.answer("Меню не найдено!", show_alert=True)
        return

    # Collect all dishes
    all_dishes = []
    for day in menu.content.get("days", []):
        for meal in day.get("meals", []):
            # Only free plan hides dinner recipes
            if plan == "free" and meal.get("meal_type") == "dinner":
                continue
            # trial and paid: full access
            for dish in meal.get("dishes", []):
                all_dishes.append({
                    "name": dish.get("name", ""),
                    "meal": meal.get("meal_name", ""),
                    "day": day.get("date_label", f"День {day['day']}")
                })

    if not all_dishes:
        await call.answer("Нет доступных блюд для рецептов.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    # Show first 10 dishes to avoid overflow
    for i, dish in enumerate(all_dishes[:10]):
        label = f"{dish['name'][:30]}..."[:35] if len(dish['name']) > 30 else dish['name']
        builder.button(text=f"🍴 {label}", callback_data=f"recipe_dish:{menu_id}:{i}")
    builder.adjust(1)

    text = (
        f"🍴 <b>Рецепты для меню</b>\n\n"
        f"Показано {min(10, len(all_dishes))} из {len(all_dishes)} блюд.\n"
        f"Выберите блюдо для поиска рецепта:"
        + ("\n\n🔒 <i>Рецепты ужинов доступны в триал и PRO</i>" if plan == "free" else "")
    )

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("recipe_dish:"))
async def get_dish_recipe(call: CallbackQuery):
    parts = call.data.split(":")
    menu_id = int(parts[1])
    dish_idx = int(parts[2])

    async with AsyncSessionLocal() as session:
        plan = await get_user_plan(session, call.from_user.id)
        menu = await session.get(Menu, menu_id)

    all_dishes = []
    for day in menu.content.get("days", []):
        for meal in day.get("meals", []):
            if plan == "free" and meal.get("meal_type") == "dinner":
                continue
            for dish in meal.get("dishes", []):
                all_dishes.append(dish.get("name", ""))

    if dish_idx >= len(all_dishes):
        await call.answer("Блюдо не найдено!", show_alert=True)
        return

    dish_name = all_dishes[dish_idx]
    await call.answer("Ищу рецепты...")

    try:
        queries = await suggest_recipe_queries(dish_name)
    except Exception:
        queries = [f"рецепт {dish_name}", f"{dish_name} пошаговый рецепт"]

    builder = InlineKeyboardBuilder()
    for q in queries:
        encoded = urllib.parse.quote_plus(q)
        url = f"https://www.google.com/search?q={encoded}"
        builder.button(text=f"🔍 {q}", url=url)
    builder.adjust(1)

    await call.message.edit_text(
        f"🍴 <b>Рецепты для: {dish_name}</b>\n\n"
        f"Нажмите на ссылку для поиска рецепта в Google:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
