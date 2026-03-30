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
user_data = {}       # Текущий правильный ответ
user_stats = {}      # Статистика {user_id: {"correct": 0, "wrong": 0}}
user_queue = {}      # Очередь слов для пользователя (чтобы не повторялись)
user_wrong = {}      # Слова, которые пользователь ответил неправильно

# --- КНОПКИ ---
def build_keyboard(choices, include_reset=False):
    buttons = [InlineKeyboardButton(text=c, callback_data=c) for c in choices]
    
    # 2 кнопки в ряд
    keyboard_rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    
    # Кнопка сброса
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
    user_wrong[user_id] = []

# --- ГЕНЕРАЦИЯ ВОПРОСА ---
def generate_question(user_id):
    # Если очередь слов пуста, создаём новую из всех слов
    if user_id not in user_queue or not user_queue[user_id]:
        user_queue[user_id] = words.copy()
        random.shuffle(user_queue[user_id])
    
    # Выбираем слово
    word = user_queue[user_id].pop(0)
    correct = word["ru"]
    
    # Все остальные переводы
    all_translations = [w["ru"] for w in words if w["ru"] != correct]
    choices = random.sample(all_translations, min(3, len(all_translations)))
    choices.append(correct)
    random.shuffle(choices)
    
    # Сохраняем текущий правильный ответ
    user_data[user_id] = correct
    return word, choices, correct

# --- ОТПРАВКА ВОПРОСА ---
async def send_question(user_id, message=None):
    word, choices, correct = generate_question(user_id)
    text = f"{word['he']} — {word['tr']}\nВыберите правильный перевод:"
    
    markup = build_keyboard(choices, include_reset=True)
    
    if message:  # если есть объект сообщения, редактируем
        await message.answer(text, reply_markup=markup)
    else:  # новое сообщение
        await bot.send_message(user_id, text, reply_markup=markup)

# --- СТАРТ ---
@dp.message(Command(commands=["start", "restart"]))
async def start(message: types.Message):
    reset_stats(message.from_user.id)  # при старте сбросим очередь
    await send_question(message.from_user.id)

# --- ОТВЕТ ---
@dp.callback_query()
async def answer(call: types.CallbackQuery):
    user_id = call.from_user.id

    # --- Сброс статистики ---
    if call.data == "reset":
        reset_stats(user_id)
        await call.message.edit_text("📊 Статистика обнулена!")
        await send_question(user_id)
        return

    correct = user_data.get(user_id)
    
    if call.data == correct:
        update_stats(user_id, True)
        result_text = f"✅ Верно! {correct}"
    else:
        update_stats(user_id, False)
        result_text = f"❌ Неверно! Правильный ответ: {correct}"
        # Добавляем слово в массив неправильных 5 раз для повторения
        if user_id not in user_wrong:
            user_wrong[user_id] = []
        for _ in range(5):
            user_wrong[user_id].append(next(w for w in words if w["ru"] == correct))
    
    correct_count, wrong_count = get_stats(user_id)
    await call.message.edit_text(
        f"{result_text}\n\n📊 Статистика:\n✅ {correct_count} | ❌ {wrong_count}"
    )

    # --- Следующий вопрос ---
    # Если очередь пустая и есть неправильные слова, ставим их в очередь
    if user_id not in user_queue:
        user_queue[user_id] = []
    if not user_queue[user_id] and user_id in user_wrong and user_wrong[user_id]:
        random.shuffle(user_wrong[user_id])
        user_queue[user_id] = user_wrong[user_id]
        user_wrong[user_id] = []
    
    await send_question(user_id)

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
