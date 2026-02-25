import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import AsyncSessionLocal, Menu, get_user_plan
from handlers.menu_generation import format_menu_summary
from keyboards.keyboards import menu_actions_keyboard
from sqlalchemy import update

logger = logging.getLogger(__name__)
router = Router()


class EditMenuFSM(StatesGroup):
    choose_day   = State()
    choose_meal  = State()
    choose_dish  = State()
    new_dish     = State()


@router.callback_query(F.data.startswith("edit_menu:"))
async def start_edit(call: CallbackQuery, state: FSMContext):
    menu_id = int(call.data.split(":")[1])
    await state.update_data(edit_menu_id=menu_id)

    async with AsyncSessionLocal() as session:
        menu = await session.get(Menu, menu_id)

    if not menu:
        await call.answer("Меню не найдено!", show_alert=True)
        return

    days = menu.content.get("days", [])
    lines = ["<b>Редактирование меню</b>\n\nВыберите номер дня:\n"]
    for d in days:
        day_num   = d.get("day", "")
        day_label = d.get("date_label", f"День {day_num}")
        lines.append(f"  <b>{day_num}</b> — {day_label}")

    await state.set_state(EditMenuFSM.choose_day)
    await call.message.edit_text("\n".join(lines), parse_mode="HTML")


@router.message(EditMenuFSM.choose_day)
async def choose_day_handler(message: Message, state: FSMContext):
    try:
        day_num = int(message.text.strip())
    except ValueError:
        await message.answer("Введите номер дня цифрой (например: <code>1</code>):",
                             parse_mode="HTML")
        return

    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        menu = await session.get(Menu, data["edit_menu_id"])

    day = next((d for d in menu.content["days"] if d["day"] == day_num), None)
    if not day:
        await message.answer("День не найден. Введите корректный номер:")
        return

    await state.update_data(edit_day=day_num)

    # Нумеруем приёмы пищи цифрами
    meals = day.get("meals", [])
    lines = [f"<b>День {day_num} — приёмы пищи:</b>\n"]
    for i, m in enumerate(meals, start=1):
        meal_name = m.get("meal_name", m["meal_type"])
        time_str  = m.get("time", "")
        lines.append(f"  <b>{i}</b> — {meal_name} {time_str}")
    lines.append("\nВведите номер приёма пищи:")

    await state.update_data(edit_day_meals=[m["meal_type"] for m in meals])
    await state.set_state(EditMenuFSM.choose_meal)
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(EditMenuFSM.choose_meal)
async def choose_meal_handler(message: Message, state: FSMContext):
    try:
        meal_idx = int(message.text.strip()) - 1
    except ValueError:
        await message.answer("Введите номер приёма пищи цифрой (например: <code>1</code>):",
                             parse_mode="HTML")
        return

    data = await state.get_data()
    meals_list = data.get("edit_day_meals", [])
    if meal_idx < 0 or meal_idx >= len(meals_list):
        await message.answer(f"Введите число от 1 до {len(meals_list)}:")
        return

    meal_type = meals_list[meal_idx]
    await state.update_data(edit_meal=meal_type)

    async with AsyncSessionLocal() as session:
        menu = await session.get(Menu, data["edit_menu_id"])

    day  = next((d for d in menu.content["days"] if d["day"] == data["edit_day"]), None)
    meal = next((m for m in day["meals"] if m["meal_type"] == meal_type), None)
    if not meal:
        await message.answer("Приём пищи не найден. Попробуйте снова:")
        return

    dishes = meal.get("dishes", [])
    lines  = [f"<b>Блюда:</b>\n"]
    for i, d in enumerate(dishes, start=1):
        lines.append(f"  <b>{i}</b> — {d.get('name', '')}")
    lines.append("\nВведите номер блюда для замены:")

    await state.set_state(EditMenuFSM.choose_dish)
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(EditMenuFSM.choose_dish)
async def choose_dish_handler(message: Message, state: FSMContext):
    try:
        dish_idx = int(message.text.strip()) - 1
    except ValueError:
        await message.answer("Введите номер блюда цифрой (например: <code>1</code>):",
                             parse_mode="HTML")
        return

    await state.update_data(edit_dish_idx=dish_idx)
    await state.set_state(EditMenuFSM.new_dish)
    await message.answer(
        "Введите название нового блюда:\n\n"
        "Например: <code>Греческий салат</code>",
        parse_mode="HTML"
    )


@router.message(EditMenuFSM.new_dish)
async def apply_dish_edit(message: Message, state: FSMContext):
    new_dish_name = message.text.strip()
    data = await state.get_data()

    await message.answer("Обновляю блюдо...")

    async with AsyncSessionLocal() as session:
        menu = await session.get(Menu, data["edit_menu_id"])
        plan = await get_user_plan(session, message.from_user.id)

        content = menu.content
        day  = next((d for d in content["days"] if d["day"] == data["edit_day"]), None)
        meal = next((m for m in day["meals"] if m["meal_type"] == data["edit_meal"]), None)

        if meal and 0 <= data["edit_dish_idx"] < len(meal["dishes"]):
            meal["dishes"][data["edit_dish_idx"]] = {
                "name":                 new_dish_name,
                "description":          "Блюдо добавлено пользователем",
                "ingredients":          [],
                "calories_per_serving": None,
                "proteins":             None,
                "fats":                 None,
                "carbs":                None,
            }

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
