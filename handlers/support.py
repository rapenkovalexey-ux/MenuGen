import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.email_service import send_support_email
from keyboards.keyboards import support_keyboard, main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()

SUBJECT_MAP = {
    "bug": "🐛 Ошибка в боте",
    "idea": "💡 Предложение по улучшению",
    "question": "❓ Вопрос",
    "payment": "💳 Вопрос по оплате",
}


class SupportFSM(StatesGroup):
    subject = State()
    message = State()


@router.message(F.text == "📞 Поддержка")
async def support_menu(message: Message):
    await message.answer(
        "📞 <b>Поддержка</b>\n\n"
        "Выберите тему обращения:",
        parse_mode="HTML",
        reply_markup=support_keyboard()
    )


@router.callback_query(F.data.startswith("support:"))
async def support_category(call: CallbackQuery, state: FSMContext):
    category = call.data.split(":")[1]
    subject = SUBJECT_MAP.get(category, "Обращение")
    await state.update_data(support_subject=subject)
    await state.set_state(SupportFSM.message)
    await call.message.edit_text(
        f"✍️ <b>{subject}</b>\n\n"
        f"Опишите вашу проблему или вопрос подробно.\n"
        f"Мы ответим вам в ближайшее время:",
        parse_mode="HTML"
    )


@router.message(SupportFSM.message)
async def process_support_message(message: Message, state: FSMContext):
    data = await state.get_data()
    subject = data.get("support_subject", "Обращение")

    success = await send_support_email(
        user_id=message.from_user.id,
        username=message.from_user.username or str(message.from_user.id),
        subject=subject,
        message=message.text
    )

    if success:
        await message.answer(
            "✅ <b>Сообщение отправлено!</b>\n\n"
            "Мы получили ваше обращение и ответим как можно скорее.\n"
            "Обычно отвечаем в течение 24 часов.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard()
        )
    else:
        await message.answer(
            "⚠️ <b>Не удалось отправить сообщение</b>\n\n"
            "Попробуйте позже или обратитесь напрямую.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard()
        )
    await state.clear()
