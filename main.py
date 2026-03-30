import asyncio
import json
import os
import random
import sqlite3

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- ТОКЕН И БОТ ---
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect("words.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS stats (
    user_id INTEGER PRIMARY KEY,
    correct INTEGER DEFAULT 0,
    wrong INTEGER DEFAULT 0
)
""")
conn.commit()

# --- ЗАГРУЗКА СЛОВ ИЗ JSON ---
with open("words.json", "r", encoding="utf-8") as f:
    words = json.load(f)

user_data = {}

# --- ГЕНЕРАЦИЯ ВОПРОСА ---
def generate_question():
    word = random.choice(words)
    correct = word["ru"]
    all_translations = [w["ru"] for w in words if w["ru"] != correct]
    choices = random.sample(all_translations, min(3, len(all_translations)))
    choices.append(correct)
    random.shuffle(choices)
    return word, choices, correct

# --- БОЛЬШИЕ КНОПКИ (2x2 + Сброс) ---
def build_keyboard(choices):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        types.KeyboardButton(choices[0]),
        types.KeyboardButton(choices[1])
    )
    keyboard.add(
        types.KeyboardButton(choices[2]),
        types.KeyboardButton(choices[3])
    )
    keyboard.add(types.KeyboardButton("🔄 Сбросить статистику"))
    return keyboard

# --- СТАТИСТИКА ---
def update_stats(user_id, is_correct):
    cursor.execute("SELECT correct, wrong FROM stats WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute(
            "INSERT INTO stats (user_id, correct, wrong) VALUES (?, ?, ?)",
            (user_id, 1 if is_correct else 0, 0 if is_correct else 1)
        )
    else:
        if is_correct:
            cursor.execute("UPDATE stats SET correct = correct + 1 WHERE user_id=?", (user_id,))
        else:
            cursor.execute("UPDATE stats SET wrong = wrong + 1 WHERE user_id=?", (user_id,))
    conn.commit()

def get_stats(user_id):
    cursor.execute("SELECT correct, wrong FROM stats WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row if row else (0, 0)

def reset_stats(user_id):
    cursor.execute("DELETE FROM stats WHERE user_id=?", (user_id,))
    conn.commit()

# --- СТАРТ / РЕСТАРТ ---
@dp.message(Command(commands=["start", "restart"]))
async def start(message: types.Message):
    word, choices, correct = generate_question()
    user_data[message.from_user.id] = correct
    text = f"{word['he']} — {word['tr']}\nВыберите перевод:"
    await message.answer(text, reply_markup=build_keyboard(choices))

# --- ОБРАБОТКА ОТВЕТОВ ---
@dp.message()
async def handle_answer(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    if text == "🔄 Сбросить статистику":
        reset_stats(user_id)
        await message.answer("♻️ Статистика обнулена!", reply_markup=types.ReplyKeyboardRemove())
        # сразу задаём новый вопрос
        word, choices, correct = generate_question()
        user_data[user_id] = correct
        await message.answer(f"{word['he']} — {word['tr']}\nВыберите перевод:", reply_markup=build_keyboard(choices))
        return

    correct = user_data.get(user_id)
    if correct is None:
        # Если нет текущего вопроса
        word, choices, correct = generate_question()
        user_data[user_id] = correct
        await message.answer(f"{word['he']} — {word['tr']}\nВыберите перевод:", reply_markup=build_keyboard(choices))
        return

    if text == correct:
        update_stats(user_id, True)
        result_text = f"✅ Верно! {correct}"
    else:
        update_stats(user_id, False)
        result_text = f"❌ Неверно! Правильный ответ: {correct}"

    correct_count, wrong_count = get_stats(user_id)
    await message.answer(
        f"{result_text}\n\n📊 Статистика:\n✅ {correct_count} | ❌ {wrong_count}"
    )

    # Новый вопрос
    word, choices, correct = generate_question()
    user_data[user_id] = correct
    await message.answer(f"{word['he']} — {word['tr']}\nВыберите перевод:", reply_markup=build_keyboard(choices))

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
