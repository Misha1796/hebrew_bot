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
user_data = {}          # Текущий правильный ответ
user_stats = {}         # Статистика {user_id: {"correct": 0, "wrong": 0}}
user_queue = {}         # Очередь слов для повторов {user_id: [words...]}

# --- ГЕНЕРАЦИЯ ВОПРОСА ---
def generate_question_for_user(user_id):
    if user_id not in user_queue or not user_queue[user_id]:
        # если очередь пуста, создаем список всех слов и перемешиваем
        user_queue[user_id] = words.copy()
        random.shuffle(user_queue[user_id])
    # берём первое слово из очереди
    word = user_queue[user_id].pop(0)
    correct = word["ru"]
    # создаем варианты ответов
    all_translations = [w["ru"] for w in words if w["ru"] != correct]
    choices = random.sample(all_translations, min(3, len(all_translations)))
    choices.append(correct)
    random.shuffle(choices)
    return word, choices, correct

# --- КНОПКИ ---
def build_keyboard(choices, include_reset=False):
    buttons = [InlineKeyboardButton(text=c, callback_data=c) for c in choices]
    keyboard_rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    if include_reset:
        keyboard_rows.append([InlineKeyboardButton(text="🔄 Сбросить статистику", callback_data="reset")])
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
    user_queue[user_id] = []

# --- СТАРТ ---
@dp.message(Command(commands=["start", "restart"]))
async def start(message: types.Message):
    user_id = message.from_user.id
    word, choices, correct = generate_question_for_user(user_id)
    user_data[user_id] = correct
    text = f"{word['he']} — {word['tr']}\nВыберите правильный перевод:"
    await message.answer(text, reply_markup=build_keyboard(choices, include_reset=True))

# --- ОТВЕТ ---
@dp.callback_query()
async def answer(call: types.CallbackQuery):
    user_id = call.from_user.id

    # --- Сброс статистики ---
    if call.data == "reset":
        reset_stats(user_id)
        await call.message.edit_text("📊 Статистика и очередь слов обнулены!")
        word, choices, correct = generate_question_for_user(user_id)
        user_data[user_id] = correct
        await call.message.answer(
            f"{word['he']} — {word['tr']}",
            reply_markup=build_keyboard(choices, include_reset=True)
        )
        return

    # --- Проверка ответа ---
    correct = user_data.get(user_id)
    if call.data == correct:
        update_stats(user_id, True)
        result_text = f"✅ Верно! {correct}"
    else:
        update_stats(user_id, False)
        result_text = f"❌ Неверно! Правильный ответ: {correct}"
        # добавляем слово обратно в очередь 5 раз
        if user_id not in user_queue:
            user_queue[user_id] = []
        for _ in range(5):
            user_queue[user_id].append(next(w for w in words if w["ru"] == correct))
        random.shuffle(user_queue[user_id])

    correct_count, wrong_count = get_stats(user_id)
    await call.message.edit_text(
        f"{result_text}\n\n📊 Статистика:\n✅ {correct_count} | ❌ {wrong_count}"
    )

    # --- Следующий вопрос ---
    word, choices, correct = generate_question_for_user(user_id)
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
