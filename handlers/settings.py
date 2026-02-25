from aiogram import Router, F
from aiogram.types import Message

router = Router()

# Placeholder - settings can be extended
@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message):
    await message.answer("⚙️ Настройки будут добавлены в следующем обновлении.")
