import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database.db import AsyncSessionLocal, Menu, User, get_user_plan
from services.groq_service import generate_nutrition_tip, substitute_ingredient
from keyboards.keyboards import menu_actions_keyboard, main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


class SubstituteFSM(StatesGroup):
    ingredient = State()


# ── DAILY TIP ──────────────────────────────────────────────────────────────────
@router.message(F.text == "💡 Совет дня")
async def daily_tip(message: Message):
    await message.answer("⏳ Генерирую совет...")
    try:
        tip = await generate_nutrition_tip()
        await message.answer(
            f"💡 <b>Совет по питанию</b>\n\n{tip}\n\n"
            f"<i>Хотите ещё? Нажмите кнопку снова!</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer("❌ Ошибка при получении совета. Попробуйте снова.")


# ── INGREDIENT SUBSTITUTION ───────────────────────────────────────────────────
@router.message(F.text == "🔄 Замена ингредиента")
async def substitute_start(message: Message, state: FSMContext):
    await state.set_state(SubstituteFSM.ingredient)
    await message.answer(
        "🔄 <b>Замена ингредиента</b>\n\n"
        "Введите название продукта, который хотите заменить:\n\n"
        "Например: <code>сливочное масло</code>, <code>пшеничная мука</code>, <code>яйца</code>",
        parse_mode="HTML"
    )


@router.message(SubstituteFSM.ingredient)
async def get_substitutes(message: Message, state: FSMContext):
    ingredient = message.text.strip()
    await state.clear()

    async with AsyncSessionLocal() as session:
        plan = await get_user_plan(session, message.from_user.id)

    # Get diet from last menu
    diet = "правильное"
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            menu_result = await session.execute(
                select(Menu).where(Menu.user_id == user.id).order_by(Menu.created_at.desc()).limit(1)
            )
            last_menu = menu_result.scalar_one_or_none()
            if last_menu:
                diet = last_menu.diet_type

    await message.answer(f"⏳ Ищу замены для «{ingredient}»...")
    try:
        result = await substitute_ingredient(ingredient, diet)
        subs = result.get("substitutes", [])
        notes = result.get("notes", "")
        text = (
            f"🔄 <b>Замены для: {ingredient}</b>\n\n"
            + "\n".join([f"✅ {s}" for s in subs])
            + (f"\n\n📝 {notes}" if notes else "")
        )
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer("❌ Ошибка. Попробуйте снова.")


# ── MY MENUS ──────────────────────────────────────────────────────────────────
@router.message(F.text == "📋 Мои меню")
async def my_menus(message: Message):
    async with AsyncSessionLocal() as session:
        plan = await get_user_plan(session, message.from_user.id)
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("Профиль не найден.")
            return

        menus_result = await session.execute(
            select(Menu).where(Menu.user_id == user.id).order_by(Menu.created_at.desc()).limit(5)
        )
        menus = menus_result.scalars().all()

    if not menus:
        await message.answer(
            "📋 У вас ещё нет созданных меню.\n\n"
            "Нажмите «🍽️ Создать меню» чтобы начать!",
            reply_markup=main_menu_keyboard()
        )
        return

    from keyboards.keyboards import DIET_BUTTONS
    diet_labels = {v: k for k, v in [(b[0], b[1]) for b in DIET_BUTTONS]}

    for menu in menus:
        diet_name = diet_labels.get(menu.diet_type, menu.diet_type)
        text = (
            f"🍽️ <b>{diet_name}</b>\n"
            f"📅 {menu.num_days} дней | 👥 {menu.num_people} чел.\n"
            f"🕐 {menu.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=menu_actions_keyboard(menu.id, plan)
        )


# ── WATER TRACKER TIP ─────────────────────────────────────────────────────────
@router.message(F.text.lower().contains("вода") | F.text.lower().contains("воды"))
async def water_tip(message: Message):
    await message.answer(
        "💧 <b>Норма воды</b>\n\n"
        "Рекомендуемое потребление: <b>30-35 мл на кг веса</b>\n\n"
        "Для человека 70 кг: ~2-2.5 литра в день\n"
        "Не считая воду в еде и напитках.\n\n"
        "💡 Совет: выпивайте стакан воды за 30 минут до каждого приёма пищи!",
        parse_mode="HTML"
    )
