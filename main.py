from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
import asyncio
import os

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

# --- Кнопка возврата в меню ---
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

# --- Обработка кнопок главного меню ---
@dp.callback_query()
async def menu_handler(call: types.CallbackQuery):
    user_id = call.from_user.id
    if call.data == "back_main":
        await call.message.edit_text("📚 Главное меню", reply_markup=main_menu())
        return

    # Примеры режимов
    if call.data == "mode_trainer":
        await call.message.edit_text("📝 Режим: Тренажёр слов", reply_markup=back_to_menu())
    elif call.data == "mode_future":
        await call.message.edit_text("🔮 Режим: Будущее время", reply_markup=back_to_menu())
    elif call.data == "mode_past":
        await call.message.edit_text("⏳ Режим: Прошедшее время", reply_markup=back_to_menu())
    elif call.data == "mode_adjectives":
        await call.message.edit_text("🖌 Режим: Прилагательные", reply_markup=back_to_menu())
    elif call.data == "mode_prepositions":
        await call.message.edit_text("🔗 Режим: Союзы / предлоги", reply_markup=back_to_menu())
    elif call.data == "mode_materials":
        await call.message.edit_text("📚 Учебные материалы", reply_markup=back_to_menu())

# --- Запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
