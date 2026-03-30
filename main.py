import asyncio
import random
import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command

# --- ТОКЕН ---
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ЗАГРУЗКА СЛОВ ИЗ JSON ---
words_file = "words.json"
if not os.path.exists(words_file):
    # Если файла нет, создаем минимальный пример
    sample_words = [
        {"he": "לעשות", "tr": "лаасот", "ru": "делать"},
        {"he": "לאכול", "tr": "леэхоль", "ru": "есть"},
        {"he": "לשתות", "tr": "лиштот", "ru": "пить"},
        {"he": "לישון", "tr": "лишон", "ru": "спать"}
    ]
    with open(words_file, "w", encoding="utf-8") as f:
        json.dump(sample_words, f, ensure_ascii=False, indent=4)

with open(words_file, "r", encoding="utf-8") as f:
    words = json.load(f)

# --- ДАННЫЕ ПОЛЬЗОВАТЕЛЕЙ ---
user_data = {}       # Текущий правильный ответ
user_stats = {}      # Статистика {user_id: {"correct": 0, "wrong": 0}}

# --- ГЕНЕРАЦИЯ ВОПРОСА ---
def generate_question():
    word = random.choice(words)
    correct = word["ru"]
    # Все остальные переводы
    all_translations = [w["ru"] for w in words if w["ru"] != correct]
    choices = random.sample(all_translations, min(3, len(all_translations)))
    choices.append(correct)
    random.shuffle(choices)
    return word, choices, correct

# --- КНОПКИ ---
def build_keyboard(choices, include_reset=False):
    # Растягиваем кнопки с помощью EM SPACE (\u2003)
    def pad_text(text, length=20):
        if len(text) >= length:
            return text
        return text + "\u2003" * (length - len(text))

    buttons = [InlineKeyboardButton(text=pad_text(c), callback_data=c) for c in choices]

    # Разбиваем на строки по 2 кнопки
    keyboard_rows = []
    for i in range(0, len(buttons), 2):
        keyboard_rows.append(buttons[i:i+2])

    # Кнопка "Сбросить" тоже растягиваем
    if include_reset:
        reset_btn = InlineKeyboardButton(text=pad_text("🔄 Сбросить статистику"), callback_data="reset")
        keyboard_rows.append([reset_btn])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

# --- СТАТИСТИКА ---
def update_stats(user_id, is_correct):
    if user_id not in user_stats:
        user_stats[user_id] = {"correct": 0, "wrong": 0}
    if is_correct:
        user_stats[user_id]["correct"] += 1
    else:
        user_stats[user_id]["wrong"] += 1

def get_stats(user_id):
    if user_id not in user_stats:
        user_stats[user_id] = {"correct": 0, "wrong": 0}
    return user_stats[user_id]["correct"], user_stats[user_id]["wrong"]

def reset_stats(user_id):
    user_stats[user_id] = {"correct": 0, "wrong": 0}

# --- СТАРТ ---
@dp.message(Command(commands=["start", "restart"]))
async def start(message: types.Message):
    word, choices, correct = generate_question()
    user_data[message.from_user.id] = correct
    text = f"{word['he']} — {word['tr']}\nВыберите правильный перевод:"
    await message.answer(text, reply_markup=build_keyboard(choices, include_reset=True))

# --- ОТВЕТ ---
@dp.callback_query()
async def answer(call: types.CallbackQuery):
    user_id = call.from_user.id

    # --- Сброс статистики ---
    if call.data == "reset":
        reset_stats(user_id)
        await call.message.edit_text("📊 Статистика обнулена!")
        # задаем новый вопрос
        word, choices, correct = generate_question()
        user_data[user_id] = correct
        await call.message.answer(
            f"{word['he']} — {word['tr']}",
            reply_markup=build_keyboard(choices, include_reset=True)
        )
        return

    # --- Проверка ответа ---
    correct_answer = user_data.get(user_id)
    if call.data == correct_answer:
        update_stats(user_id, True)
        result_text = f"✅ Верно! {call.message.text.splitlines()[0]} — {correct_answer}"
    else:
        update_stats(user_id, False)
        # Показываем слово на иврите и правильный перевод
        word_he_tr = next((w for w in words if w["ru"] == correct_answer), None)
        if word_he_tr:
            result_text = f"❌ Неверно! {word_he_tr['he']} — {correct_answer}"
        else:
            result_text = f"❌ Неверно! Правильный ответ: {correct_answer}"

    correct_count, wrong_count = get_stats(user_id)
    await call.message.edit_text(
        f"{result_text}\n\n📊 Статистика:\n✅ {correct_count} | ❌ {wrong_count}"
    )

    # --- Следующий вопрос ---
    word, choices, correct = generate_question()
    user_data[user_id] = correct
    await call.message.answer(
        f"{word['he']} — {word['tr']}",
        reply_markup=build_keyboard(choices, include_reset=True)
    )

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
