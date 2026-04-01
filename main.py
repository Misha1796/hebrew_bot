import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()  # здесь не передаем bot!

# --- Главное меню ---
def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1️⃣ Тренажёр слов", callback_data="mode_trainer"),
                InlineKeyboardButton(text="🔮 Будущее время", callback_data="mode_future")
            ],
            [
                InlineKeyboardButton(text="⏳ Прошедшее время", callback_data="mode_past"),
                InlineKeyboardButton(text="🖌 Прилагательные", callback_data="mode_adjectives")
            ],
            [
                InlineKeyboardButton(text="🔗 Союзы / предлоги", callback_data="mode_prepositions"),
                InlineKeyboardButton(text="📚 Учебные материалы", callback_data="mode_materials")
            ]
        ]
    )

# --- Кнопка возврата ---
def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
        ]
    )

# --- Старт ---
@dp.message(Command(commands=["start"]))
async def start(message: types.Message):
    await message.answer("📚 Главное меню", reply_markup=main_menu())

# --- Обработка кнопок ---
@dp.callback_query()
async def callback_handler(call: types.CallbackQuery):
    data = call.data

    if data == "back_main":
        await call.message.edit_text("📚 Главное меню", reply_markup=main_menu())
        return

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
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
