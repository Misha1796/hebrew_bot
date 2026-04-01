import asyncio
import random
import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ЗАГРУЗКА ---
with open("words.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# --- ДАННЫЕ ---
user_mode = {}
user_data = {}
user_stats = {}
user_repeat = {}

# --- МЕНЮ ---
def main_menu():
    buttons = [
        [InlineKeyboardButton(text="📘 Тренажёр", callback_data="mode_trainer")],
        [InlineKeyboardButton(text="🔮 Будущее", callback_data="mode_future")],
        [InlineKeyboardButton(text="⏳ Прошедшее", callback_data="mode_past")],
        [InlineKeyboardButton(text="🧩 Прилагательные", callback_data="mode_adjectives")],
        [InlineKeyboardButton(text="🔗 Связки", callback_data="mode_connectors")],
        [InlineKeyboardButton(text="📚 Обучение", callback_data="learning")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- КНОПКИ ---
def build_keyboard(choices, include_back=True):
    def pad(text, l=25):
        return text + "\u2003" * max(0, l - len(text))

    buttons = []
    for c in choices:
        if isinstance(c, dict):
            text = f"{c['he']} — {c['tr']}"
            callback = c["he"]
        else:
            text = c
            callback = c

        buttons.append(InlineKeyboardButton(text=pad(text), callback_data=callback))

    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]

    if include_back:
        rows.append([InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")])

    return InlineKeyboardMarkup(inline_keyboard=rows)

# --- СТАТИСТИКА ---
def update_stats(user_id, correct, word):
    user_stats.setdefault(user_id, {"c": 0, "w": 0})
    user_repeat.setdefault(user_id, [])

    if correct:
        user_stats[user_id]["c"] += 1
        if word in user_repeat[user_id]:
            user_repeat[user_id].remove(word)
    else:
        user_stats[user_id]["w"] += 1
        user_repeat[user_id] += [word] * 3  # умный повтор

def stats(user_id):
    s = user_stats.get(user_id, {"c": 0, "w": 0})
    return s["c"], s["w"]

# --- ГЕНЕРАЦИЯ ---
def generate_question(user_id, mode):
    pool = data[mode].copy()

    # добавляем ошибки
    if user_repeat.get(user_id):
        pool += user_repeat[user_id]

    item = random.choice(pool)

    if mode == "trainer":
        correct = item["ru"]
        choices = random.sample([w["ru"] for w in data["trainer"] if w["ru"] != correct], 3)
        choices.append(correct)
        random.shuffle(choices)
        return item, choices, correct

    else:
        return item, item["options"], item["correct"]

# --- СТАРТ ---
@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("Выбери режим:", reply_markup=main_menu())

# --- МЕНЮ ---
@dp.callback_query(lambda c: c.data == "menu")
async def menu(call: types.CallbackQuery):
    await call.message.edit_text("Выбери режим:", reply_markup=main_menu())

# --- ОБУЧЕНИЕ ---
@dp.callback_query(lambda c: c.data == "learning")
async def learning(call: types.CallbackQuery):
    text = "\n".join(data["learning"])
    await call.message.edit_text(text, reply_markup=main_menu())

# --- ВЫБОР РЕЖИМА ---
@dp.callback_query(lambda c: c.data.startswith("mode_"))
async def set_mode(call: types.CallbackQuery):
    mode = call.data.replace("mode_", "")
    user_mode[call.from_user.id] = mode

    word, choices, correct = generate_question(call.from_user.id, mode)
    user_data[call.from_user.id] = correct

    if mode == "trainer":
        text = f"{word['he']} — {word['tr']}"
    else:
        text = word["question"]

    await call.message.edit_text(text, reply_markup=build_keyboard(choices))

# --- ОТВЕТ ---
@dp.callback_query()
async def answer(call: types.CallbackQuery):
    user_id = call.from_user.id

    if call.data == "menu":
        return

    mode = user_mode.get(user_id)
    correct = user_data.get(user_id)

    # найти слово
    word_obj = None
    for item in data[mode]:
        if mode == "trainer":
            if item["ru"] == correct:
                word_obj = item
        else:
            if item["correct"] == correct:
                word_obj = item

    is_correct = call.data == correct
    update_stats(user_id, is_correct, word_obj)

    if mode == "trainer":
        result = f"{word_obj['he']} — {word_obj['tr']} = {word_obj['ru']}"
    else:
        result = f"{word_obj['he']} — {word_obj['tr']} = {word_obj['question']}"

    text = "✅ Верно!\n" if is_correct else "❌ Неверно!\n"
    c, w = stats(user_id)

    await call.message.edit_text(f"{text}{result}\n\n📊 {c} | {w}")

    # следующий вопрос
    word, choices, correct = generate_question(user_id, mode)
    user_data[user_id] = correct

    if mode == "trainer":
        text = f"{word['he']} — {word['tr']}"
    else:
        text = word["question"]

    await call.message.answer(text, reply_markup=build_keyboard(choices))

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
