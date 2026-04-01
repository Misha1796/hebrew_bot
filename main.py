import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- Токен ---
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()  # В aiogram 3.x бот не передаётся в Dispatcher

# --- Загрузка слов из файла ---
WORDS_FILE = "words.json"

try:
    with open(WORDS_FILE, "r", encoding="utf-8") as f:
        words_data = json.load(f)
except FileNotFoundError:
    print(f"Файл {WORDS_FILE} не найден!")
    words_data = {}

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

    # Названия режимов
    modes = {
        "mode_trainer": "📝 Режим: Тренажёр слов",
        "mode_future": "🔮 Режим: Будущее время",
        "mode_past": "⏳ Режим: Прошедшее время",
        "mode_adjectives": "🖌 Режим: Прилагательные",
        "mode_prepositions": "🔗 Режим: Союзы / предлоги",
        "mode_materials": "📚 Учебные материалы"
    }

    text = modes.get(data, "Неизвестный режим")

    # Подгружаем слова для режимов
    if data == "mode_trainer":
        sample_words = words_data.get("trainer", [])
    elif data == "mode_future":
        sample_words = words_data.get("future", [])
    elif data == "mode_past":
        sample_words = words_data.get("past", [])
    elif data == "mode_adjectives":
        sample_words = words_data.get("adjectives", [])
    elif data == "mode_prepositions":
        sample_words = words_data.get("prepositions", [])
    elif data == "mode_materials":
        sample_words = words_data.get("materials", [])
    else:
        sample_words = []

    if sample_words:
        # Выводим первые 5 слов для примера
        text += "\n\n"
        for w in sample_words[:5]:
            text += f"{w.get('he', '')} - {w.get('tr', '')} - {w.get('ru', '')}\n"
    else:
        text += "\n\nСлова не найдены!"

    await call.message.edit_text(text, reply_markup=back_to_menu())

# --- Запуск ---
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
