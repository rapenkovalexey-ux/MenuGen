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
    eaters_info = State()
    days = State()
    days_custom = State()
    meals_select = State()
    meal_times = State()
    confirm = State()
    generating = State()


MEAL_NAMES = {
    "breakfast": "Р—Р°РІС‚СЂР°Рє",
    "brunch": "Р’С‚РѕСЂРѕР№ Р·Р°РІС‚СЂР°Рє",
    "lunch": "РћР±РµРґ",
    "snack": "РџРµСЂРµРєСѓСЃ",
    "dinner": "РЈР¶РёРЅ",
}

DEFAULT_TIMES = {
    "breakfast": "08:00",
    "brunch": "11:00",
    "lunch": "13:00",
    "snack": "16:00",
    "dinner": "19:00",
}


@router.message(F.text == "\U0001f37d\ufe0f РЎРѕР·РґР°С‚СЊ РјРµРЅСЋ")
async def start_menu_creation(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(MenuFSM.diet)
    await message.answer(
        "<b>РЁР°Рі 1/5: Р’С‹Р±РµСЂРёС‚Рµ СЂРµР¶РёРј РїРёС‚Р°РЅРёСЏ</b>\n\n"
        "РћС‚ СЌС‚РѕРіРѕ Р·Р°РІРёСЃРёС‚ РїРѕРґР±РѕСЂ Р±Р»СЋРґ Рё РєР°Р»РѕСЂРёР№РЅРѕСЃС‚СЊ:",
        parse_mode="HTML",
        reply_markup=diet_keyboard()
    )


@router.callback_query(MenuFSM.diet, F.data.startswith("diet:"))
async def process_diet(call: CallbackQuery, state: FSMContext):
    diet = call.data.split(":")[1]
    await state.update_data(diet=diet)
    await state.set_state(MenuFSM.people_count)
    await call.message.edit_text(
        "<b>РЁР°Рі 2/5: РЎРєРѕР»СЊРєРѕ С‡РµР»РѕРІРµРє Р±СѓРґРµС‚ РїРёС‚Р°С‚СЊСЃСЏ?</b>",
        parse_mode="HTML",
        reply_markup=people_keyboard()
    )


@router.callback_query(MenuFSM.people_count, F.data.startswith("people:"))
async def process_people(call: CallbackQuery, state: FSMContext):
    val = call.data.split(":")[1]
    if val == "custom":
        await state.set_state(MenuFSM.people_custom)
        await call.message.edit_text("Р’РІРµРґРёС‚Рµ РєРѕР»РёС‡РµСЃС‚РІРѕ С‡РµР»РѕРІРµРє (С‡РёСЃР»Рѕ РѕС‚ 1 РґРѕ 50):")
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
            await message.answer("Р’РІРµРґРёС‚Рµ С‡РёСЃР»Рѕ РѕС‚ 1 РґРѕ 50:")
            return
    except ValueError:
        await message.answer("РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РІРІРµРґРёС‚Рµ С‡РёСЃР»Рѕ:")
        return
    await state.update_data(num_people=count, eaters=[], current_eater=0)
    await state.set_state(MenuFSM.eaters_info)
    await ask_eater_info(message, state, 0, count)


async def ask_eater_info(message_or_call, state: FSMContext, index: int, total: int):
    num = index + 1
    msg = (
        "<b>РРЅС„РѕСЂРјР°С†РёСЏ Рѕ С‡РµР»РѕРІРµРєРµ " + str(num) + " РёР· " + str(total) + "</b>\n\n"
        "Р’РІРµРґРёС‚Рµ РґР°РЅРЅС‹Рµ РІ С„РѕСЂРјР°С‚Рµ:\n"
        "<code>РРјСЏ, РІРѕР·СЂР°СЃС‚, РїСЂРµРґРїРѕС‡С‚РµРЅРёСЏ</code>\n\n"
        "РџСЂРёРјРµСЂС‹:\n"
        "- <code>РњР°СЂРёСЏ, 35, Р±РµР· РѕСЂРµС…РѕРІ</code>\n"
        "- <code>РџРµС‚СЏ, 8, Р»СЋР±РёС‚ СЃР»Р°РґРєРѕРµ Р±РµР· РѕСЃС‚СЂРѕРіРѕ</code>\n"
        "- <code>Р”РµРґСѓС€РєР°, 72, РґРёР°Р±РµС‚ 2 С‚РёРїР°</code>\n\n"
        "РР»Рё РЅР°Р¶РјРёС‚Рµ РџСЂРѕРїСѓСЃС‚РёС‚СЊ, РµСЃР»Рё Р±РµР· РѕСЃРѕР±РµРЅРЅРѕСЃС‚РµР№:"
    )
    if hasattr(message_or_call, 'edit_text'):
        await message_or_call.edit_text(
            msg, parse_mode="HTML",
            reply_markup=skip_keyboard("skip_eater:" + str(index))
        )
    else:
        await message_or_call.answer(
            msg, parse_mode="HTML",
            reply_markup=skip_keyboard("skip_eater:" + str(index))
        )


@router.callback_query(MenuFSM.eaters_info, F.data.startswith("skip_eater:"))
async def skip_eater(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = int(call.data.split(":")[1])
    eaters = data.get("eaters", [])
    eaters.append({"name": "Р§РµР»РѕРІРµРє " + str(idx + 1), "age": None, "preferences": None})
    total = data["num_people"]
    await state.update_data(eaters=eaters, current_eater=idx + 1)
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
        "name": parts[0] if len(parts) > 0 else "Р§РµР»РѕРІРµРє " + str(idx + 1),
        "age": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None,
        "preferences": ", ".join(parts[2:]) if len(parts) > 2 else None
    }
    eaters.append(eater)
    await state.update_data(eaters=eaters, current_eater=idx + 1)

    if idx + 1 < total:
        await ask_eater_info(message, state, idx + 1, total)
    else:
        await proceed_to_days(message, state)


async def proceed_to_days(message, state: FSMContext):
    data = await state.get_data()
    plan = data.get("plan", "free")
    max_days = FREE_MAX_DAYS if plan == "free" else TRIAL_MAX_DAYS
    await state.set_state(MenuFSM.days)

    if plan == "free":
        text = (
            "<b>РЁР°Рі 3/5: РќР° СЃРєРѕР»СЊРєРѕ РґРЅРµР№ СЃРѕСЃС‚Р°РІРёС‚СЊ РјРµРЅСЋ?</b>\n\n"
            "Р‘РµСЃРїР»Р°С‚РЅС‹Р№ РїР»Р°РЅ: РјР°РєСЃРёРјСѓРј " + str(FREE_MAX_DAYS) + " РґРЅСЏ. "
            "Р”Р»СЏ Р±РѕР»СЊС€РµРіРѕ вЂ” РѕС„РѕСЂРјРёС‚Рµ PRO."
        )
    else:
        text = "<b>РЁР°Рі 3/5: РќР° СЃРєРѕР»СЊРєРѕ РґРЅРµР№ СЃРѕСЃС‚Р°РІРёС‚СЊ РјРµРЅСЋ?</b>"

    await message.answer(text, parse_mode="HTML", reply_markup=days_keyboard(max_days))


@router.callback_query(MenuFSM.days, F.data.startswith("days:"))
async def process_days(call: CallbackQuery, state: FSMContext):
    val = call.data.split(":")[1]
    if val == "custom":
        await state.set_state(MenuFSM.days_custom)
        data = await state.get_data()
        plan = data.get("plan", "free")
        max_d = FREE_MAX_DAYS if plan == "free" else TRIAL_MAX_DAYS
        await call.message.edit_text("Р’РІРµРґРёС‚Рµ РєРѕР»РёС‡РµСЃС‚РІРѕ РґРЅРµР№ (1-" + str(max_d) + "):")
        return
    await state.update_data(num_days=int(val), selected_meals=[])
    await state.set_state(MenuFSM.meals_select)
    await call.message.edit_text(
        "<b>РЁР°Рі 4/5: Р’С‹Р±РµСЂРёС‚Рµ РїСЂРёС‘РјС‹ РїРёС‰Рё</b>\n\nРћС‚РјРµС‚СЊС‚Рµ РЅСѓР¶РЅС‹Рµ Рё РЅР°Р¶РјРёС‚Рµ Р“РѕС‚РѕРІРѕ:",
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
            await message.answer("Р’РІРµРґРёС‚Рµ С‡РёСЃР»Рѕ РѕС‚ 1 РґРѕ " + str(max_d) + ":")
            return
    except ValueError:
        await message.answer("РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РІРІРµРґРёС‚Рµ С‡РёСЃР»Рѕ:")
        return
    await state.update_data(num_days=days, selected_meals=[])
    await state.set_state(MenuFSM.meals_select)
    await message.answer(
        "<b>РЁР°Рі 4/5: Р’С‹Р±РµСЂРёС‚Рµ РїСЂРёС‘РјС‹ РїРёС‰Рё</b>\n\nРћС‚РјРµС‚СЊС‚Рµ РЅСѓР¶РЅС‹Рµ Рё РЅР°Р¶РјРёС‚Рµ Р“РѕС‚РѕРІРѕ:",
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
            await call.answer("Р’С‹Р±РµСЂРёС‚Рµ С…РѕС‚СЏ Р±С‹ РѕРґРёРЅ РїСЂРёС‘Рј РїРёС‰Рё!", show_alert=True)
            return
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
        lines.append("- " + MEAL_NAMES[m] + ": " + DEFAULT_TIMES[m])
    text = (
        "<b>РЁР°Рі 5/5: Р’СЂРµРјСЏ РїСЂРёС‘РјРѕРІ РїРёС‰Рё</b>\n\n"
        "РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ СѓСЃС‚Р°РЅРѕРІР»РµРЅРѕ:\n" + "\n".join(lines) +
        "\n\nРҐРѕС‚РёС‚Рµ РёР·РјРµРЅРёС‚СЊ? Р’РІРµРґРёС‚Рµ С‡РµСЂРµР· Р·Р°РїСЏС‚СѓСЋ:\n"
        "<code>Р·Р°РІС‚СЂР°Рє 09:00, РѕР±РµРґ 14:00, СѓР¶РёРЅ 20:00</code>\n\n"
        "РР»Рё РЅР°Р¶РјРёС‚Рµ РџСЂРѕРїСѓСЃС‚РёС‚СЊ РґР»СЏ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ СЃС‚Р°РЅРґР°СЂС‚РЅРѕРіРѕ РІСЂРµРјРµРЅРё:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=skip_keyboard("skip_times"))


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

    time_map = {
        "Р·Р°РІС‚СЂР°Рє": "breakfast", "РѕР±РµРґ": "lunch", "СѓР¶РёРЅ": "dinner",
        "РїРµСЂРµРєСѓСЃ": "snack", "РІС‚РѕСЂРѕР№ Р·Р°РІС‚СЂР°Рє": "brunch"
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
    diet_labels = {v: k for k, v in [(b[0], b[1]) for b in DIET_BUTTONS]}
    diet_display = diet_labels.get(diet, diet)

    eaters_lines = []
    for i, e in enumerate(eaters):
        line = "  - " + e.get("name", "Р§РµР»РѕРІРµРє " + str(i + 1))
        if e.get("age"):
            line += ", " + str(e["age"]) + " Р»РµС‚"
        if e.get("preferences"):
            line += " (" + e["preferences"] + ")"
        eaters_lines.append(line)
    eaters_str = "\n".join(eaters_lines)

    meals_lines = []
    for k, v in meals_config.items():
        meals_lines.append("  - " + MEAL_NAMES.get(k, k) + ": " + v)
    meals_str = "\n".join(meals_lines)

    text = (
        "<b>РџРѕРґС‚РІРµСЂРґРёС‚Рµ РїР°СЂР°РјРµС‚СЂС‹ РјРµРЅСЋ:</b>\n\n"
        "Р РµР¶РёРј РїРёС‚Р°РЅРёСЏ: " + diet_display + "\n"
        "РљРѕР»РёС‡РµСЃС‚РІРѕ С‡РµР»РѕРІРµРє: " + str(num_people) + "\n"
        "РљРѕР»РёС‡РµСЃС‚РІРѕ РґРЅРµР№: " + str(num_days) + "\n\n"
        "<b>Р•РґРѕРєРё:</b>\n" + eaters_str + "\n\n"
        "<b>РџСЂРёС‘РјС‹ РїРёС‰Рё:</b>\n" + meals_str + "\n\n"
        "Р’СЃС‘ РІРµСЂРЅРѕ? РќР°Р¶РјРёС‚Рµ РЎРіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ РґР»СЏ СЃРѕР·РґР°РЅРёСЏ РјРµРЅСЋ."
    )

    await state.set_state(MenuFSM.confirm)
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=confirm_cancel_keyboard("confirm_menu", "cancel_menu")
    )


@router.callback_query(MenuFSM.confirm, F.data == "cancel_menu")
async def cancel_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("РЎРѕР·РґР°РЅРёРµ РјРµРЅСЋ РѕС‚РјРµРЅРµРЅРѕ.")
    await call.message.answer("Р“Р»Р°РІРЅРѕРµ РјРµРЅСЋ:", reply_markup=main_menu_keyboard())


@router.callback_query(MenuFSM.confirm, F.data == "confirm_menu")
async def confirm_and_generate(call: CallbackQuery, state: FSMContext):
    await state.set_state(MenuFSM.generating)
    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        plan = await get_user_plan(session, call.from_user.id)
        user = await get_or_create_user(session, call.from_user.id)

    num_days = data.get("num_days", 1)
    if plan == "free" and num_days > FREE_MAX_DAYS:
        num_days = FREE_MAX_DAYS

    progress_msg = await call.message.edit_text(
        "<b>Р“РµРЅРµСЂРёСЂСѓСЋ РјРµРЅСЋ...</b>\n\n"
        "РР СЃРѕСЃС‚Р°РІР»СЏРµС‚ СЂРµС†РµРїС‚С‹ СЃРїРµС†РёР°Р»СЊРЅРѕ РґР»СЏ РІР°СЃ. "
        "Р­С‚Рѕ Р·Р°Р№РјРµС‚ 15-30 СЃРµРєСѓРЅРґ.",
        parse_mode="HTML"
    )

    try:
        menu_data = await generate_menu(
            diet_type=data.get("diet"),
            num_people=data.get("num_people", 1),
            num_days=num_days,
            meals_config=data.get("meals_config", {
                "breakfast": "08:00",
                "lunch": "13:00",
                "dinner": "19:00"
            }),
            eaters=data.get("eaters", []),
            plan=plan
        )

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

        summary = format_menu_summary(menu_data, plan)
        from keyboards.keyboards import menu_actions_keyboard
        await progress_msg.edit_text(
            summary,
            parse_mode="HTML",
            reply_markup=menu_actions_keyboard(menu_id, plan)
        )

    except Exception as e:
        logger.error("Menu generation error: " + str(e))
        await progress_msg.edit_text(
            "<b>РћС€РёР±РєР° РїСЂРё РіРµРЅРµСЂР°С†РёРё РјРµРЅСЋ.</b>\n\n"
            "РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РїРѕРїСЂРѕР±СѓР№С‚Рµ СЃРЅРѕРІР°.\n\n"
            "Р”РµС‚Р°Р»Рё: " + str(e)[:200],
            parse_mode="HTML"
        )
    finally:
        await state.clear()


def format_menu_summary(menu_data: dict, plan: str) -> str:
    lines = ["<b>РњРµРЅСЋ РіРѕС‚РѕРІРѕ!</b>\n"]
    for day in menu_data.get("days", []):
        day_num = str(day.get("day", ""))
        day_label = day.get("date_label", "Р”РµРЅСЊ " + day_num)
        lines.append("\n<b>" + day_label + "</b>")
        for meal in day.get("meals", []):
            meal_name = meal.get("meal_name", "")
            meal_time = meal.get("time", "")
            dishes = [d.get("name", "") for d in meal.get("dishes", [])]
            cal = meal.get("total_calories", "")
            if cal and plan != "free":
                cal_str = " (" + str(cal) + " РєРєР°Р»)"
            else:
                cal_str = ""
            lines.append("  " + meal_name + " " + meal_time + cal_str)
            for d in dishes:
                lines.append("    - " + d)

    if plan == "free":
        lines.append("\n\n<i>РљР°Р»РѕСЂРёР№РЅРѕСЃС‚СЊ Рё СЃРїРёСЃРѕРє РїРѕРєСѓРїРѕРє РґРѕСЃС‚СѓРїРЅС‹ РІ PRO</i>")

    return "\n".join(lines)


@router.message(Command("cancel"))
@router.message(F.text == "/cancel")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Р”РµР№СЃС‚РІРёРµ РѕС‚РјРµРЅРµРЅРѕ.", reply_markup=main_menu_keyboard())
