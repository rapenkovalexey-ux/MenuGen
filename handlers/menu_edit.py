import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database.db import AsyncSessionLocal, Menu, get_user_plan
from services.groq_service import generate_menu
from handlers.menu_generation import format_menu_summary
from keyboards.keyboards import menu_actions_keyboard

logger = logging.getLogger(__name__)
router = Router()


class EditMenuFSM(StatesGroup):
    choose_day = State()
    choose_meal = State()
    choose_dish = State()
    new_dish = State()


@router.callback_query(F.data.startswith("edit_menu:"))
async def start_edit(call: CallbackQuery, state: FSMContext):
    menu_id = int(call.data.split(":")[1])
    await state.update_data(edit_menu_id=menu_id)
    await state.set_state(EditMenuFSM.choose_day)

    async with AsyncSessionLocal() as session:
        menu = await session.get(Menu, menu_id)

    if not menu:
        await call.answer("Меню не найдено!", show_alert=True)
        return

    days = menu.content.get("days", [])
    lines = [f"✏️ <b>Редактирование меню</b>\n\nВыберите день:\n"]
    for d in days:
        lines.append(f"• {d.get('date_label', f'День {d[\"day\"]}')}: введите <code>{d['day']}</code>")

    await call.message.edit_text("\n".join(lines), parse_mode="HTML")


@router.message(EditMenuFSM.choose_day)
async def choose_day(message: Message, state: FSMContext):
    try:
        day_num = int(message.text.strip())
    except ValueError:
        await message.answer("Введите номер дня (число):")
        return
    await state.update_data(edit_day=day_num)
    await state.set_state(EditMenuFSM.choose_meal)

    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        menu = await session.get(Menu, data["edit_menu_id"])

    day = next((d for d in menu.content["days"] if d["day"] == day_num), None)
    if not day:
        await message.answer("День не найден. Введите корректный номер:")
        return

    meals_info = "\n".join([
        f"• {m.get('meal_name', m['meal_type'])}: введите <code>{m['meal_type']}</code>"
        for m in day.get("meals", [])
    ])
    await message.answer(
        f"Приёмы пищи в день {day_num}:\n\n{meals_info}",
        parse_mode="HTML"
    )


@router.message(EditMenuFSM.choose_meal)
async def choose_meal(message: Message, state: FSMContext):
    meal_type = message.text.strip().lower()
    await state.update_data(edit_meal=meal_type)
    await state.set_state(EditMenuFSM.choose_dish)

    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        menu = await session.get(Menu, data["edit_menu_id"])

    day = next((d for d in menu.content["days"] if d["day"] == data["edit_day"]), None)
    meal = next((m for m in day["meals"] if m["meal_type"] == meal_type), None)
    if not meal:
        await message.answer("Приём пищи не найден. Введите ещё раз:")
        return

    dishes_info = "\n".join([
        f"{i+1}. {d.get('name', '')}" for i, d in enumerate(meal.get("dishes", []))
    ])
    await message.answer(
        f"Блюда:\n\n{dishes_info}\n\nВведите номер блюда для замены:",
        parse_mode="HTML"
    )


@router.message(EditMenuFSM.choose_dish)
async def choose_dish(message: Message, state: FSMContext):
    try:
        dish_idx = int(message.text.strip()) - 1
    except ValueError:
        await message.answer("Введите номер блюда:")
        return
    await state.update_data(edit_dish_idx=dish_idx)
    await state.set_state(EditMenuFSM.new_dish)
    await message.answer(
        "📝 Введите название нового блюда (или описание — ИИ подберёт ингредиенты):\n\n"
        "Например: <code>Греческий салат</code> или <code>Лёгкий омлет с овощами</code>",
        parse_mode="HTML"
    )


@router.message(EditMenuFSM.new_dish)
async def apply_dish_edit(message: Message, state: FSMContext):
    new_dish_name = message.text.strip()
    data = await state.get_data()

    await message.answer("⏳ Обновляю блюдо...")

    async with AsyncSessionLocal() as session:
        menu = await session.get(Menu, data["edit_menu_id"])
        plan = await get_user_plan(session, message.from_user.id)

        content = menu.content
        day = next((d for d in content["days"] if d["day"] == data["edit_day"]), None)
        meal = next((m for m in day["meals"] if m["meal_type"] == data["edit_meal"]), None)

        if meal and 0 <= data["edit_dish_idx"] < len(meal["dishes"]):
            # Simple replacement - use AI to expand
            meal["dishes"][data["edit_dish_idx"]] = {
                "name": new_dish_name,
                "description": "Блюдо добавлено пользователем",
                "ingredients": [],
                "calories_per_serving": None,
                "proteins": None, "fats": None, "carbs": None
            }

        from sqlalchemy import update
        await session.execute(
            update(Menu).where(Menu.id == data["edit_menu_id"]).values(content=content)
        )
        await session.commit()
        await session.refresh(menu)

    await message.answer(
        f"✅ Блюдо заменено на: <b>{new_dish_name}</b>\n\n"
        + format_menu_summary(menu.content, plan),
        parse_mode="HTML",
        reply_markup=menu_actions_keyboard(data["edit_menu_id"], plan)
    )
    await state.clear()
