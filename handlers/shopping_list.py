import io
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from database.db import AsyncSessionLocal, Menu, get_user_plan
from services.groq_service import generate_shopping_list
from services.pdf_service import generate_shopping_pdf, generate_menu_pdf

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("shopping:"))
async def send_shopping_list(call: CallbackQuery):
    menu_id = int(call.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        plan = await get_user_plan(session, call.from_user.id)
        menu = await session.get(Menu, menu_id)

    if not menu:
        await call.answer("Меню не найдено!", show_alert=True)
        return

    if plan == "free":
        await call.answer("🔒 Список покупок доступен в триал или PRO версии!", show_alert=True)
        return

    await call.message.edit_text("🛒 <b>Формирую список покупок...</b>", parse_mode="HTML")

    try:
        # Check if shopping list already generated
        if menu.shopping_list:
            shopping_data = menu.shopping_list
        else:
            shopping_data = await generate_shopping_list(menu.content, menu.num_people)
            # Save
            async with AsyncSessionLocal() as session:
                from sqlalchemy import update
                await session.execute(
                    update(Menu).where(Menu.id == menu_id).values(shopping_list=shopping_data)
                )
                await session.commit()

        meta = {
            "diet_type": menu.diet_type,
            "num_days": menu.num_days,
            "num_people": menu.num_people
        }
        pdf_bytes = generate_shopping_pdf(shopping_data, meta)

        await call.message.answer_document(
            BufferedInputFile(pdf_bytes, filename=f"shopping_list_menu_{menu_id}.pdf"),
            caption="🛒 <b>Ваш список покупок готов!</b>\n\nРаспечатайте или используйте прямо в магазине ✅",
            parse_mode="HTML"
        )
        await call.message.edit_text("✅ Список покупок отправлен!")

    except Exception as e:
        logger.error(f"Shopping list error: {e}")
        await call.message.edit_text(f"❌ Ошибка при создании списка: {str(e)[:200]}")


@router.callback_query(F.data.startswith("menu_pdf:"))
async def send_menu_pdf(call: CallbackQuery):
    menu_id = int(call.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        plan = await get_user_plan(session, call.from_user.id)
        menu = await session.get(Menu, menu_id)

    if not menu:
        await call.answer("Меню не найдено!", show_alert=True)
        return

    await call.message.edit_text("📄 <b>Формирую PDF меню...</b>", parse_mode="HTML")

    try:
        meta = {
            "diet_type": menu.diet_type,
            "num_days": menu.num_days,
            "num_people": menu.num_people
        }
        pdf_bytes = generate_menu_pdf(menu.content, meta, plan)

        await call.message.answer_document(
            BufferedInputFile(pdf_bytes, filename=f"menu_{menu_id}.pdf"),
            caption="🍽️ <b>Ваше меню в PDF!</b>\n\nМожно распечатать или сохранить 📎",
            parse_mode="HTML"
        )
        await call.message.edit_text("✅ PDF меню отправлено!")

    except Exception as e:
        logger.error(f"Menu PDF error: {e}")
        await call.message.edit_text(f"❌ Ошибка: {str(e)[:200]}")


@router.callback_query(F.data.startswith("delete_menu:"))
async def delete_menu(call: CallbackQuery):
    menu_id = int(call.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        menu = await session.get(Menu, menu_id)
        if menu:
            await session.delete(menu)
            await session.commit()
    await call.message.edit_text("🗑️ Меню удалено.")
