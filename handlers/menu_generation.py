import json
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

from database.db import AsyncSessionLocal, get_user_plan, get_or_create_user, Menu
from keyboards.keyboards import (
    diet_keyboard, days_keyboard, meals_keyboard,
    people_keyboard, confirm_cancel_keyboard, skip_keyboard, main_menu_keyboard
)
from services.groq_service import generate_menu
from config import FREE_MAX_DAYS, TRIAL_MAX_DAYS

logger = logging.getLogger(__name__)
router = Router()


class MenuFSM(StatesGroup):
    diet = State()
    people_count = State()
    people_custom = State()
    eaters_info = State()      # collecting age/preferences per person
    days = State()
    days_custom = State()
    meals_select = State()
    meal_times = State()
    confirm = State()
    generating = State()


MEAL_NAMES = {
    "breakfast": "Завтрак",
    "brunch": "Второй завтрак",
    "lunch": "Обед",
    "snack": "Перекус",
    "dinner": "Ужин",
}

DEFAULT_TIMES = {
    "breakfast": "08:00",
    "brunch": "11:00",
    "lunch": "13:00",
    "snack": "16:00",
    "dinner": "19:00",
}


@router.message(F.text == "🍽️ Создать меню")
async def start_menu_creation(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(MenuFSM.diet)
    await message.answer(
        "🥗 <b>Шаг 1/5: Выберите режим питания</b>\n\n"
        "От этого зависит подбор блюд и калорийность:",
        parse_mode="HTML",
        reply_markup=diet_keyboard()
    )


@router.callback_query(MenuFSM.diet, F.data.startswith("diet:"))
async def process_diet(call: CallbackQuery, state: FSMContext):
    diet = call.data.split(":")[1]
    await state.update_data(diet=diet)
    await state.set_state(MenuFSM.people_count)
    await call.message.edit_text(
        "👥 <b>Шаг 2/5: Сколько человек будет питаться?</b>",
        parse_mode="HTML",
        reply_markup=people_keyboard()
    )


@router.callback_query(MenuFSM.people_count, F.data.startswith("people:"))
async def process_people(call: CallbackQuery, state: FSMContext):
    val = call.data.split(":")[1]
    if val == "custom":
        await state.set_state(MenuFSM.people_custom)
        await call.message.edit_text("✏️ Введите количество человек (число от 1 до 50):")
        return
    count = int(val)
    await state.update_data(num_people=count, eaters=[], current_eater=0)
    await state.set_state(MenuFSM.eaters_info)
    await ask_eater_info(call.message, state, 0, count)


@router.message(MenuFSM.people_custom)
async def process_people_custom(message: Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count < 1 or count > 50:
            await message.answer("Введите число от 1 до 50:")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число:")
        return
    await state.update_data(num_people=count, eaters=[], current_eater=0)
    await state.set_state(MenuFSM.eaters_info)
    await ask_eater_info(message, state, 0, count)


async def ask_eater_info(message_or_call, state: FSMContext, index: int, total: int):
    msg = (
        f"👤 <b>Информация о человеке {index + 1} из {total}</b>\n\n"
        f"Введите данные в формате:\n"
        f"<code>Имя, возраст, предпочтения</code>\n\n"
        f"Примеры:\n"
        f"• <code>Мария, 35, без орехов</code>\n"
        f"• <code>Петя, 8, любит сладкое без острого</code>\n"
        f"• <code>Дедушка, 72, диабет 2 типа</code>\n\n"
        f"Или нажмите «Пропустить», если без особенностей:"
    )
    if hasattr(message_or_call, 'edit_text'):
        await message_or_call.edit_text(msg, parse_mode="HTML",
                                         reply_markup=skip_keyboard(f"skip_eater:{index}"))
    else:
        await message_or_call.answer(msg, parse_mode="HTML",
                                      reply_markup=skip_keyboard(f"skip_eater:{index}"))


@router.callback_query(MenuFSM.eaters_info, F.data.startswith("skip_eater:"))
async def skip_eater(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = int(call.data.split(":")[1])
    eaters = data.get("eaters", [])
    eaters.append({"name": f"Человек {idx+1}", "age": None, "preferences": None})
    total = data["num_people"]
    await state.update_data(eaters=eaters, current_eater=idx+1)
    if idx + 1 < total:
        await ask_eater_info(call.message, state, idx + 1, total)
    else:
        await proceed_to_days(call.message, state)


@router.message(MenuFSM.eaters_info)
async def process_eater_info(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get("current_eater", 0)
    total = data["num_people"]
    eaters = data.get("eaters", [])

    text = message.text.strip()
    parts = [p.strip() for p in text.split(",")]
    eater = {
        "name": parts[0] if len(parts) > 0 else f"Человек {idx+1}",
        "age": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None,
        "preferences": ", ".join(parts[2:]) if len(parts) > 2 else None
    }
    eaters.append(eater)
    await state.update_data(eaters=eaters, current_eater=idx+1)

    if idx + 1 < total:
        await ask_eater_info(message, state, idx + 1, total)
    else:
        await proceed_to_days(message, state)


async def proceed_to_days(message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        # We need user telegram_id from state context - stored differently
        pass
    # Check plan from state data
    data = await state.get_data()
    plan = data.get("plan", "free")

    max_days = FREE_MAX_DAYS if plan == "free" else TRIAL_MAX_DAYS
    await state.set_state(MenuFSM.days)
    await message.answer(
        f"📅 <b>Шаг 3/5: На сколько дней составить меню?</b>"
        + (f"\n\n⚠️ Бесплатный план: максимум {FREE_MAX_DAYS} дня. Для большего — оформите PRO." if plan == "free" else ""),
        parse_mode="HTML",
        reply_markup=days_keyboard(max_days)
    )


@router.callback_query(MenuFSM.days, F.data.startswith("days:"))
async def process_days(call: CallbackQuery, state: FSMContext):
    val = call.data.split(":")[1]
    if val == "custom":
        await state.set_state(MenuFSM.days_custom)
        data = await state.get_data()
        plan = data.get("plan", "free")
        max_d = FREE_MAX_DAYS if plan == "free" else TRIAL_MAX_DAYS
        await call.message.edit_text(f"✏️ Введите количество дней (1–{max_d}):")
        return
    await state.update_data(num_days=int(val), selected_meals=[])
    await state.set_state(MenuFSM.meals_select)
    await call.message.edit_text(
        "🍽️ <b>Шаг 4/5: Выберите приёмы пищи</b>\n\nОтметьте нужные и нажмите «Готово»:",
        parse_mode="HTML",
        reply_markup=meals_keyboard([])
    )


@router.message(MenuFSM.days_custom)
async def process_days_custom(message: Message, state: FSMContext):
    data = await state.get_data()
    plan = data.get("plan", "free")
    max_d = FREE_MAX_DAYS if plan == "free" else TRIAL_MAX_DAYS
    try:
        days = int(message.text.strip())
        if days < 1 or days > max_d:
            await message.answer(f"Введите число от 1 до {max_d}:")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число:")
        return
    await state.update_data(num_days=days, selected_meals=[])
    await state.set_state(MenuFSM.meals_select)
    await message.answer(
        "🍽️ <b>Шаг 4/5: Выберите приёмы пищи</b>\n\nОтметьте нужные и нажмите «Готово»:",
        parse_mode="HTML",
        reply_markup=meals_keyboard([])
    )


@router.callback_query(MenuFSM.meals_select, F.data.startswith("meal:"))
async def process_meal_toggle(call: CallbackQuery, state: FSMContext):
    meal = call.data.split(":")[1]
    if meal == "done":
        data = await state.get_data()
        selected = data.get("selected_meals", [])
        if not selected:
            await call.answer("Выберите хотя бы один приём пищи!", show_alert=True)
            return
        # Ask for times
        await state.set_state(MenuFSM.meal_times)
        await ask_meal_times(call.message, selected, state)
        return

    data = await state.get_data()
    selected = data.get("selected_meals", [])
    if meal in selected:
        selected.remove(meal)
    else:
        selected.append(meal)
    await state.update_data(selected_meals=selected)
    await call.message.edit_reply_markup(reply_markup=meals_keyboard(selected))


async def ask_meal_times(message, selected_meals: list, state: FSMContext):
    lines = []
    for m in selected_meals:
        lines.append(f"• {MEAL_NAMES[m]}: {DEFAULT_TIMES[m]}")
    text = (
        "⏰ <b>Шаг 5/5: Время приёмов пищи</b>\n\n"
        "По умолчанию установлено:\n" + "\n".join(lines) +
        "\n\nХотите изменить? Введите через запятую:\n"
        "<code>завтрак 09:00, обед 14:00, ужин 20:00</code>\n\n"
        "Или нажмите «Пропустить» для использования стандартного времени:"
    )
    await message.answer(text, parse_mode="HTML",
                          reply_markup=skip_keyboard("skip_times"))


@router.callback_query(MenuFSM.meal_times, F.data == "skip_times")
async def skip_times(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_meals", [])
    meals_config = {m: DEFAULT_TIMES[m] for m in selected}
    await state.update_data(meals_config=meals_config)
    await show_confirmation(call.message, state)


@router.message(MenuFSM.meal_times)
async def process_meal_times(message: Message, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_meals", [])
    meals_config = {m: DEFAULT_TIMES[m] for m in selected}

    # Try to parse user input like "завтрак 09:00, обед 14:00"
    time_map = {
        "завтрак": "breakfast", "обед": "lunch", "ужин": "dinner",
        "перекус": "snack", "второй завтрак": "brunch"
    }
    try:
        parts = message.text.split(",")
        for part in parts:
            part = part.strip().lower()
            for ru, en in time_map.items():
                if ru in part and en in selected:
                    time_str = part.replace(ru, "").strip()
                    if ":" in time_str:
                        meals_config[en] = time_str
    except Exception:
        pass

    await state.update_data(meals_config=meals_config)
    await show_confirmation(message, state)


async def show_confirmation(message, state: FSMContext):
    data = await state.get_data()
    diet = data.get("diet", "")
    num_people = data.get("num_people", 1)
    num_days = data.get("num_days", 1)
    eaters = data.get("eaters", [])
    meals_config = data.get("meals_config", {})

    from keyboards.keyboards import DIET_BUTTONS
    diet_name = dict(DIET_BUTTONS).get(
        next((k for k, v in dict([(b[1], b[0]) for b in DIET_BUTTONS]).items() if k == diet), ""),
        diet
    )
    # Simpler lookup:
    diet_labels = {v: k for k, v in [(b[0], b[1]) for b in DIET_BUTTONS]}
    diet_display = diet_labels.get(diet, diet)

    eaters_str = "\n".join([
        f"  • {e.get('name', f'Человек {i+1}')}"
        + (f", {e['age']} лет" if e.get('age') else "")
        + (f" ({e['preferences']})" if e.get('preferences') else "")
        for i, e in enumerate(eaters)
    ])

    meals_str = "\n".join([
        f"  • {MEAL_NAMES.get(k, k)}: {v}" for k, v in meals_config.items()
    ])

    text = f"""✅ <b>Подтвердите параметры меню:</b>

🥗 Режим питания: {diet_display}
👥 Количество человек: {num_people}
📅 Количество дней: {num_days}

<b>Едоки:</b>
{eaters_str}

<b>Приёмы пищи:</b>
{meals_str}

Всё верно? Нажмите «Сгенерировать» для создания меню."""

    await state.set_state(MenuFSM.confirm)
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=confirm_cancel_keyboard("confirm_menu", "cancel_menu")
    )


@router.callback_query(MenuFSM.confirm, F.data == "cancel_menu")
async def cancel_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Создание меню отменено.")
    await call.message.answer("Главное меню:", reply_markup=main_menu_keyboard())


@router.callback_query(MenuFSM.confirm, F.data == "confirm_menu")
async def confirm_and_generate(call: CallbackQuery, state: FSMContext):
    await state.set_state(MenuFSM.generating)
    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        plan = await get_user_plan(session, call.from_user.id)
        user = await get_or_create_user(session, call.from_user.id)

    # Apply plan limits
    num_days = data.get("num_days", 1)
    if plan == "free" and num_days > FREE_MAX_DAYS:
        num_days = FREE_MAX_DAYS

    progress_msg = await call.message.edit_text(
        "⏳ <b>Генерирую меню...</b>\n\nИИ составляет рецепты специально для вас. "
        "Это займёт 15-30 секунд ☕",
        parse_mode="HTML"
    )

    try:
        menu_data = await generate_menu(
            diet_type=data.get("diet"),
            num_people=data.get("num_people", 1),
            num_days=num_days,
            meals_config=data.get("meals_config", {"breakfast": "08:00", "lunch": "13:00", "dinner": "19:00"}),
            eaters=data.get("eaters", []),
            plan=plan
        )

        # Save to DB
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            from database.db import User
            result = await session.execute(
                select(User).where(User.telegram_id == call.from_user.id)
            )
            db_user = result.scalar_one_or_none()
            menu = Menu(
                user_id=db_user.id,
                diet_type=data.get("diet"),
                num_people=data.get("num_people", 1),
                num_days=num_days,
                meals_per_day=data.get("meals_config"),
                content=menu_data,
                status="draft"
            )
            session.add(menu)
            await session.commit()
            await session.refresh(menu)
            menu_id = menu.id

        # Show summary
        summary = format_menu_summary(menu_data, plan)
        from keyboards.keyboards import menu_actions_keyboard
        await progress_msg.edit_text(
            summary,
            parse_mode="HTML",
            reply_markup=menu_actions_keyboard(menu_id, plan)
        )

    except Exception as e:
        logger.error(f"Menu generation error: {e}")
        await progress_msg.edit_text(
            "❌ Ошибка при генерации меню. Пожалуйста, попробуйте снова.\n\n"
            f"Детали: {str(e)[:200]}"
        )
    finally:
        await state.clear()


def format_menu_summary(menu_data: dict, plan: str) -> str:
    lines = ["🎉 <b>Меню готово!</b>\n"]
    for day in menu_data.get("days", []):
        lines.append(f"\n📅 <b>{day.get('date_label', f'День {day[\"day\"]}')}</b>")
        for meal in day.get("meals", []):
            meal_name = meal.get("meal_name", "")
            time = meal.get("time", "")
            dishes = [d.get("name", "") for d in meal.get("dishes", [])]
            cal = meal.get("total_calories", "")
            cal_str = f" ({cal} ккал)" if cal and plan != "free" else ""
            lines.append(f"  ⏰ {meal_name} {time}{cal_str}")
            for d in dishes:
                lines.append(f"    • {d}")

    if plan == "free":
        lines.append("\n\n🔒 <i>Калорийность и список покупок доступны в PRO</i>")

    return "\n".join(lines)


@router.message(Command("cancel"))
@router.message(F.text == "/cancel")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu_keyboard())

    
