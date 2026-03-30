import asyncio
import random
import os
import sqlite3
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command

# --- ТОКЕН ---
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect("words.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    he TEXT,
    tr TEXT,
    ru TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stats (
    user_id INTEGER,
    correct INTEGER DEFAULT 0,
    wrong INTEGER DEFAULT 0
)
""")

conn.commit()

# --- ЗАГРУЗКА СЛОВ ИЗ JSON ---
cursor.execute("SELECT COUNT(*) FROM words")
if cursor.fetchone()[0] == 0:
    with open("words.json", "r", encoding="utf-8") as f:
        words = json.load(f)

    words_data = [(w["he"], w["tr"], w["ru"]) for w in words]

    cursor.executemany(
        "INSERT INTO words (he, tr, ru) VALUES (?, ?, ?)",
        words_data
    )
    conn.commit()

user_data = {}

# --- ГЕНЕРАЦИЯ ВОПРОСА ---
def generate_question():
    cursor.execute("SELECT he, tr, ru FROM words")
    words = cursor.fetchall()

    word = random.choice(words)
    correct = word[2]

    all_translations = [w[2] for w in words if w[2] != correct]
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

# --- СТАРТ ---
@dp.message(Command(commands=["start", "restart"]))
async def start(message: types.Message):
    word, choices, correct = generate_question()
    user_data[message.from_user.id] = correct

    await message.answer(
        f"📚 {word[0]} — {word[1]}\n\nВыберите перевод:",
        reply_markup=build_keyboard(choices)
    )

# --- ОТВЕТ ---
@dp.callback_query(lambda c: c.data != "next")
async def answer(call: types.CallbackQuery):
    user_id = call.from_user.id
    correct = user_data.get(user_id)

    if call.data == correct:
        update_stats(user_id, True)
        text = f"✅ Отлично!\nПравильный ответ: {correct}"
    else:
        update_stats(user_id, False)
        text = f"❌ Ошибка!\nПравильный ответ: {correct}"

    correct_count, wrong_count = get_stats(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Дальше", callback_data="next")]
        ]
    )

    await call.message.edit_text(
        f"{text}\n\n📊 {correct_count} ✅ | {wrong_count} ❌",
        reply_markup=keyboard
    )

# --- СЛЕДУЮЩИЙ ВОПРОС ---
@dp.callback_query(lambda c: c.data == "next")
async def next_question(call: types.CallbackQuery):
    word, choices, correct = generate_question()
    user_data[call.from_user.id] = correct

    await call.message.edit_text(
        f"📚 {word[0]} — {word[1]}\n\nВыберите перевод:",
        reply_markup=build_keyboard(choices)
    )

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
