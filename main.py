import asyncio
import json
import os
import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ЗАГРУЗКА СЛОВ ---
with open("words.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# --- ДАННЫЕ ПОЛЬЗОВАТЕЛЕЙ ---
user_data = {}   # Текущий правильный ответ
user_stats = {}  # {user_id: {"correct": 0, "wrong": 0}}
error_queue = {} # {user_id: [слова для повторов]}

# --- КЛАВИАТУРА ---
def build_keyboard(choices, include_reset=False):
    buttons = []
    # добавляем невидимые пробелы, чтобы кнопки были крупнее
    for c in choices:
        display = f"{c}⠀⠀"  # два невидимых символа U+2800
        buttons.append(InlineKeyboardButton(display, callback_data=c))

    # две кнопки в ряд
    keyboard_rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]

    # кнопка сброса статистики
    if include_reset:
        keyboard_rows.append([InlineKeyboardButton("🔄 Сбросить статистику", callback_data="reset")])

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
    error_queue[user_id] = []

# --- ГЕНЕРАЦИЯ ВОПРОСА ---
def generate_question(user_id, mode):
    # Сначала проверяем ошибки
    if user_id in error_queue and error_queue[user_id]:
        item = error_queue[user_id].pop(0)
    else:
        item = random.choice(data[mode])

    correct = item["ru"]
    
    # Генерация вариантов
    other_choices = [w["ru"] for w in data[mode] if w["ru"] != correct]
    n_choices = min(3, len(other_choices))
    choices = random.sample(other_choices, n_choices) + [correct]
    random.shuffle(choices)

    return item, choices, correct

# --- МЕНЮ ---
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("1️⃣ Тренажёр слов", callback_data="mode_trainer")],
        [InlineKeyboardButton("2️⃣ Будущее время", callback_data="mode_future")],
        [InlineKeyboardButton("3️⃣ Прошедшее время", callback_data="mode_past")],
        [InlineKeyboardButton("4️⃣ Прилагательные", callback_data="mode_adjectives")],
        [InlineKeyboardButton("5️⃣ Связующие слова", callback_data="mode_connectors")]
    ])
    return keyboard

# --- СТАРТ ---
@dp.message(Command(commands=["start", "restart"]))
async def start(message: types.Message):
    await message.answer("📚 Главное меню", reply_markup=main_menu())

# --- ВЫБОР РЕЖИМА ---
@dp.callback_query()
async def set_mode(call: types.CallbackQuery):
    user_id = call.from_user.id
    mode_map = {
        "mode_trainer": "trainer",
        "mode_future": "future",
        "mode_past": "past",
        "mode_adjectives": "adjectives",
        "mode_connectors": "connectors"
    }

    if call.data in mode_map:
        mode = mode_map[call.data]
        item, choices, correct = generate_question(user_id, mode)
        user_data[user_id] = {"correct": correct, "mode": mode}

        # Текст вопроса
        if mode == "trainer":
            text = f"{item['he']} — {item['tr']}\nВыберите правильный перевод:"
        else:
            # показываем транскрипцию только в кнопках
            text = f"{item['he']} — Выберите правильный вариант:"

        await call.message.edit_text(text, reply_markup=build_keyboard(choices, include_reset=True))

    # Сброс статистики
    elif call.data == "reset":
        reset_stats(user_id)
        await call.message.edit_text("📊 Статистика обнулена!")
        await call.message.answer("📚 Главное меню", reply_markup=main_menu())

    # Проверка ответа
    else:
        correct = user_data[user_id]["correct"]
        mode = user_data[user_id]["mode"]
        if call.data == correct:
            update_stats(user_id, True)
            result_text = f"✅ Верно! {user_data[user_id]['correct']}"
        else:
            update_stats(user_id, False)
            result_text = f"❌ Неверно! Правильный ответ: {user_data[user_id]['correct']}"
            # добавляем слово в очередь повторов 5 раз
            error_queue.setdefault(user_id, []).extend([{"he": item["he"], "tr": item.get("tr", ""), "ru": correct}] * 5)

        correct_count, wrong_count = get_stats(user_id)
        await call.message.edit_text(f"{result_text}\n\n📊 Статистика:\n✅ {correct_count} | ❌ {wrong_count}")

        # Следующий вопрос
        item, choices, correct = generate_question(user_id, mode)
        user_data[user_id] = {"correct": correct, "mode": mode}
        if mode == "trainer":
            text = f"{item['he']} — {item['tr']}\nВыберите правильный перевод:"
        else:
            text = f"{item['he']} — Выберите правильный вариант:"
        await call.message.answer(text, reply_markup=build_keyboard(choices, include_reset=True))

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
