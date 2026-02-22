from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from database.db import get_or_create_user, get_user_plan, AsyncSessionLocal
from keyboards.keyboards import main_menu_keyboard, subscription_keyboard

router = Router()

WELCOME_TEXT = """👋 Привет, {name}!

Я <b>МенюПро</b> — твой персональный помощник по питанию на базе ИИ.

🍽️ <b>Что я умею:</b>
• Составлять меню на день, неделю или месяц
• Учитывать режим питания, возраст и предпочтения
• Считать калории и КБЖУ каждого блюда
• Формировать список покупок в PDF
• Подбирать рецепты для блюд
• Давать советы по правильному питанию

📋 <b>Твой план:</b> {plan_emoji} {plan_name}

Используй меню ниже для начала работы 👇"""

PLAN_INFO = {
    "free": ("🆓", "Бесплатный", "До 3 дней | Без калорий ужина | Без списка покупок"),
    "trial": ("🎁", "Триал (10 дней)", "Полный доступ ко всем функциям"),
    "paid": ("💎", "PRO", "Полный доступ ко всем функциям"),
}


@router.message(CommandStart())
async def cmd_start(message: Message):
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name
        )
        plan = await get_user_plan(session, message.from_user.id)

    emoji, plan_name, _ = PLAN_INFO.get(plan, PLAN_INFO["free"])
    await message.answer(
        WELCOME_TEXT.format(
            name=message.from_user.first_name,
            plan_emoji=emoji,
            plan_name=plan_name
        ),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )


@router.message(F.text == "ℹ️ Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message):
    text = """📖 <b>Справка по боту МенюПро</b>

<b>Основные команды:</b>
🍽️ <b>Создать меню</b> — запустить мастер создания меню
👤 <b>Мой профиль</b> — просмотр настроек и плана
💎 <b>Подписка</b> — управление подпиской
📋 <b>Мои меню</b> — история созданных меню
💡 <b>Совет дня</b> — получить совет по питанию
🔄 <b>Замена ингредиента</b> — найти замену продукту
📞 <b>Поддержка</b> — связаться с нами

<b>Планы:</b>
🆓 <b>Бесплатный</b> — меню до 3 дней, без калорий ужина, без PDF
🎁 <b>Триал</b> — 10 дней полного доступа (бесплатно)
💎 <b>PRO</b> — полный доступ, 299₽/мес

/start — главное меню
/help — эта справка
/cancel — отменить текущее действие"""
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "👤 Мой профиль")
async def my_profile(message: Message):
    async with AsyncSessionLocal() as session:
        plan = await get_user_plan(session, message.from_user.id)
        from sqlalchemy import select
        from database.db import User, EaterProfile
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

    emoji, plan_name, features = PLAN_INFO.get(plan, PLAN_INFO["free"])

    profile_text = f"""👤 <b>Ваш профиль</b>

🆔 ID: <code>{message.from_user.id}</code>
📛 Имя: {message.from_user.full_name}
{emoji} План: <b>{plan_name}</b>
✨ Возможности: {features}"""

    if plan == "paid" and user and user.paid_until:
        profile_text += f"\n📅 Подписка до: {user.paid_until.strftime('%d.%m.%Y')}"
    elif plan == "trial" and user and user.trial_end:
        profile_text += f"\n📅 Триал до: {user.trial_end.strftime('%d.%m.%Y')}"

    await message.answer(profile_text, parse_mode="HTML",
                         reply_markup=subscription_keyboard(plan))
