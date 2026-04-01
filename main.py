import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Главное меню ---
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("1️⃣ Тренажёр слов", callback_data="mode_trainer"),
        InlineKeyboardButton("🔮 Будущее время", callback_data="mode_future"),
        InlineKeyboardButton("⏳ Прошедшее время", callback_data="mode_past"),
        InlineKeyboardButton("🖌 Прилагательные", callback_data="mode_adjectives"),
        InlineKeyboardButton("🔗 Союзы / предлоги", callback_data="mode_prepositions"),
        InlineKeyboardButton("📚 Учебные материалы", callback_data="mode_materials")
    )
    return keyboard

# --- Кнопка возврата ---
def back_to_menu():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")
    )
    return keyboard

# --- Старт ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📚 Главное меню", reply_markup=main_menu())

# --- Обработка кнопок ---
@dp.callback_query()
async def callback_handler(call: types.CallbackQuery):
    data = call.data

    if data == "back_main":
        await call.message.edit_text("📚 Главное меню", reply_markup=main_menu())
        return

    # Режимы
    modes = {
        "mode_trainer": "📝 Режим: Тренажёр слов",
        "mode_future": "🔮 Режим: Будущее время",
        "mode_past": "⏳ Режим: Прошедшее время",
        "mode_adjectives": "🖌 Режим: Прилагательные",
        "mode_prepositions": "🔗 Режим: Союзы / предлоги",
        "mode_materials": "📚 Учебные материалы"
    }

    if data in modes:
        await call.message.edit_text(modes[data], reply_markup=back_to_menu())

# --- Запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
