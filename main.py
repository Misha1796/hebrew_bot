import asyncio
import random
import os
import json
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command

# --- Токен ---
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
    # создаём варианты ответов
    all_translations = [w["ru"] for w in words if w["ru"] != correct]
    choices = random.sample(all_translations, min(3, len(all_translations)))
    choices.append(correct)
    random.shuffle(choices)
    return word, choices, correct

# --- КНОПКИ ---
def build_keyboard(choices):
    buttons = [InlineKeyboardButton(text=c, callback_data=c) for c in choices]
    return InlineKeyboardMarkup(
        inline_keyboard=[buttons[i:i+2] for i in range(0, len(buttons), 2)]
    )

# --- СТАТИСТИКА ---
def update_stats(user_id, is_correct):
    cursor.execute("SELECT correct, wrong FROM stats WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        if is_correct:
            cursor.execute("INSERT INTO stats (user_id, correct, wrong) VALUES (?, 1, 0)", (user_id,))
        else:
            cursor.execute("INSERT INTO stats (user_id, correct, wrong) VALUES (?, 0, 1)", (user_id,))
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

def reset_stats_db(user_id):
    cursor.execute("DELETE FROM stats WHERE user_id=?", (user_id,))
    conn.commit()

# --- СТАРТ ---
@dp.message(Command(commands=["start", "restart"]))
async def start(message: types.Message):
    word, choices, correct = generate_question()
    user_data[message.from_user.id] = correct
    text = f"{word['he']} — {word['tr']}\nВыберите перевод:"
    # добавим кнопку "Сбросить статистику"
    reset_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сбросить статистику", callback_data="reset")]
    ])
    await message.answer(text, reply_markup=build_keyboard(choices))
    await message.answer("📌 Также вы можете сбросить статистику:", reply_markup=reset_button)

# --- ОТВЕТЫ НА ВАРИАНТЫ ---
@dp.callback_query()
async def answer(call: types.CallbackQuery):
    user_id = call.from_user.id

    if call.data == "reset":
        reset_stats_db(user_id)
        await call.message.answer("📊 Статистика сброшена!")
        return

    correct = user_data.get(user_id)
    if call.data == correct:
        update_stats(user_id, True)
        result_text = f"✅ Верно! {correct}"
    else:
        update_stats(user_id, False)
        result_text = f"❌ Неверно! Правильный ответ: {correct}"

    correct_count, wrong_count = get_stats(user_id)
    await call.message.edit_text(
        f"{result_text}\n\n📊 Статистика:\n✅ {correct_count} | ❌ {wrong_count}"
    )

    # следующий вопрос
    word, choices, correct = generate_question()
    user_data[user_id] = correct
    await call.message.answer(
        f"{word['he']} — {word['tr']}",
        reply_markup=build_keyboard(choices)
    )

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
