import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, LabeledPrice, PreCheckoutQuery
from sqlalchemy import select, update
from database.db import AsyncSessionLocal, User, Payment, get_user_plan
from keyboards.keyboards import main_menu_keyboard, subscription_keyboard
from config import SUBSCRIPTION_PRICE_RUB, PAYMENT_TOKEN, TRIAL_DAYS

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "💎 Подписка")
async def subscription_menu(message: Message):
    async with AsyncSessionLocal() as session:
        plan = await get_user_plan(session, message.from_user.id)

    plan_info = {
        "free": "🆓 Бесплатный план",
        "trial": "🎁 Триал период",
        "paid": "💎 PRO подписка",
    }

    features_free = """🆓 <b>Бесплатный план:</b>
• Меню до 3 дней
• 3 приёма пищи
• Без калорийности ужина
• Без списка покупок
• Без PDF
• Без рецептов ужинов"""

    features_pro = """💎 <b>PRO план — 299₽/мес:</b>
• Меню до 31 дня
• До 5 приёмов пищи
• Полная калорийность всех блюд
• Список покупок в PDF
• Меню в PDF
• Рецепты всех блюд
• Замена ингредиентов
• Приоритетная поддержка"""

    text = (
        f"💎 <b>Управление подпиской</b>\n\n"
        f"Ваш план: <b>{plan_info.get(plan, plan)}</b>\n\n"
        f"{features_free}\n\n{features_pro}"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=subscription_keyboard(plan))


@router.callback_query(F.data == "sub:trial")
async def activate_trial(call: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == call.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await call.answer("Ошибка: пользователь не найден", show_alert=True)
            return

        if user.plan in ("trial", "paid"):
            await call.answer("Триал уже был активирован или у вас PRO подписка!", show_alert=True)
            return

        now = datetime.utcnow()
        user.plan = "trial"
        user.trial_start = now
        user.trial_end = now + timedelta(days=TRIAL_DAYS)
        await session.commit()

    await call.message.edit_text(
        f"🎉 <b>Триал активирован!</b>\n\n"
        f"У вас {TRIAL_DAYS} дней полного доступа ко всем функциям бота.\n"
        f"Наслаждайтесь PRO возможностями!\n\n"
        f"После окончания триала вы сможете оформить подписку за {SUBSCRIPTION_PRICE_RUB}₽/мес.",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "sub:pay")
async def initiate_payment(call: CallbackQuery):
    if not PAYMENT_TOKEN:
        await call.message.edit_text(
            "💳 <b>Оплата PRO подписки</b>\n\n"
            f"Стоимость: <b>{SUBSCRIPTION_PRICE_RUB}₽/месяц</b>\n\n"
            "Для оплаты напишите в поддержку через меню 📞\n"
            "Мы поможем оформить подписку вручную.",
            parse_mode="HTML"
        )
        return

    await call.message.answer_invoice(
        title="PRO подписка — МенюПро",
        description=f"Полный доступ на 30 дней: меню до 31 дня, PDF, список покупок, рецепты",
        payload=f"sub_{call.from_user.id}",
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label="PRO подписка (30 дней)", amount=SUBSCRIPTION_PRICE_RUB * 100)],
        start_parameter="subscription",
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def payment_success(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            now = datetime.utcnow()
            if user.paid_until and user.paid_until > now:
                user.paid_until += timedelta(days=30)
            else:
                user.paid_until = now + timedelta(days=30)
            user.plan = "paid"

            payment = Payment(
                user_id=user.id,
                amount=SUBSCRIPTION_PRICE_RUB,
                currency="RUB",
                status="success",
                payment_id=message.successful_payment.telegram_payment_charge_id
            )
            session.add(payment)
            await session.commit()

    await message.answer(
        "🎉 <b>Оплата прошла успешно!</b>\n\n"
        "💎 Вы теперь PRO пользователь!\n"
        "Подписка активна на 30 дней.\n\n"
        "Пользуйтесь всеми возможностями бота!",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )


@router.callback_query(F.data == "upgrade")
async def prompt_upgrade(call: CallbackQuery):
    await call.answer(
        "💎 Эта функция доступна в PRO плане!\n"
        "Нажмите '💎 Подписка' в меню для оформления.",
        show_alert=True
    )
