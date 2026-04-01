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
    # пример структуры для всех режимов
    sample_words = {
        "trainer": [
            {"he": "לעשות", "tr": "лаасот", "ru": "делать"},
            {"he": "לאכול", "tr": "леэхоль", "ru": "есть"}
        ],
        "future": [
            {
                "he": "לעשות",
                "correct": "אעשה",
                "options": [
                    {"text": "אעשה — ээсэ", "value": "אעשה"},
                    {"text": "עשיתי — асити", "value": "עשיתי"},
                    {"text": "עושה — осе", "value": "עושה"},
                    {"text": "יעשה — яасэ", "value": "יעשה"}
                ]
            }
        ],
        "past": [],
        "adjectives": [],
        "prepositions": []
    }
    with open(words_file, "w", encoding="utf-8") as f:
        json.dump(sample_words, f, ensure_ascii=False, indent=4)

with open(words_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# --- ДАННЫЕ ПОЛЬЗОВАТЕЛЕЙ ---
user_data = {}       # текущий правильный ответ
user_stats = {}      # статистика {user_id: {"correct": 0, "wrong": 0}}
user_errors = {}     # ошибки для повторов

# --- МЕНЮ ---
def main_menu():
    buttons = [
        [InlineKeyboardButton("1️⃣ Тренажёр слов", callback_data="mode_trainer")],
        [InlineKeyboardButton("2️⃣ Будущее время", callback_data="mode_future")],
        [InlineKeyboardButton("3️⃣ Прошедшее время", callback_data="mode_past")],
        [InlineKeyboardButton("4️⃣ Учебные материалы", callback_data="mode_materials")],
        [InlineKeyboardButton("5️⃣ Прилагательные", callback_data="mode_adjectives")],
        [InlineKeyboardButton("6️⃣ Местоимения и предлоги", callback_data="mode_prepositions")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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
    user_errors[user_id] = []

# --- КНОПКИ ---
def build_keyboard(choices, include_reset=False):
    buttons = []

    for c in choices:
        if isinstance(c, dict):
            text = c["text"]
            value = c["value"]
        else:
            text = value = c
        # добавим невидимые символы для увеличения размера кнопки
        buttons.append(
            InlineKeyboardButton(text=f"{text}⠀⠀⠀", callback_data=value)
        )

    keyboard_rows = []
    for i in range(0, len(buttons), 2):
        keyboard_rows.append(buttons[i:i+2])

    if include_reset:
        keyboard_rows.append([InlineKeyboardButton("🔄 Сброс", callback_data="reset")])
        keyboard_rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

# --- ГЕНЕРАЦИЯ ВОПРОСА ---
def generate_question(user_id, mode):
    items = data.get(mode, [])
    
    # проверяем ошибки для повторов
    errors = user_errors.get(user_id, [])
    if errors:
        item = errors.pop(0)
        user_errors[user_id] = errors
    else:
        item = random.choice(items)
    
    if mode == "trainer":
        correct = item["ru"]
        wrong_answers = [w["ru"] for w in items if "ru" in w and w["ru"] != correct]
        choices = random.sample(wrong_answers, min(3, len(wrong_answers)))
        choices.append(correct)
        random.shuffle(choices)
        return item, choices, correct
    else:
        correct = item["correct"]
        choices = item["options"].copy()
        random.shuffle(choices)
        return item, choices, correct

# --- СТАРТ ---
@dp.message(Command(commands=["start", "restart"]))
async def start(message: types.Message):
    await message.answer("📚 Главное меню", reply_markup=main_menu())

# --- ВЫБОР РЕЖИМА ---
@dp.callback_query()
async def set_mode(call: types.CallbackQuery):
    user_id = call.from_user.id
    data_call = call.data

    if data_call == "main":
        await call.message.edit_text("📚 Главное меню", reply_markup=main_menu())
        return

    if data_call == "reset":
        reset_stats(user_id)
        await call.message.edit_text("📊 Статистика обнулена!")
        await call.message.answer("📚 Главное меню", reply_markup=main_menu())
        return

    if data_call.startswith("mode_"):
        mode = data_call.replace("mode_", "")
        word, choices, correct = generate_question(user_id, mode)
        user_data[user_id] = {"correct": correct, "mode": mode}

        if mode == "trainer":
            text = f"{word['he']} — {word['tr']}\nВыберите правильный перевод:"
        else:
            text = f"{word['he']}\nВыберите правильный вариант:"

        await call.message.edit_text(text, reply_markup=build_keyboard(choices, include_reset=True))

    else:
        # --- ОБРАБОТКА ОТВЕТА ---
        current = user_data.get(user_id)
        if not current:
            await call.message.answer("❗ Сначала выберите режим")
            return

        correct = current["correct"]
        mode = current["mode"]

        if call.data == correct:
            update_stats(user_id, True)
            result_text = f"✅ Верно!\n{correct}" if mode != "trainer" else f"✅ Верно! {correct}"
        else:
            update_stats(user_id, False)
            result_text = f"❌ Неверно! Правильный ответ: {correct}"
            # повтор ошибок до 5 раз
            user_errors.setdefault(user_id, []).extend([current]*5)

        correct_count, wrong_count = get_stats(user_id)
        await call.message.edit_text(f"{result_text}\n\n📊 Статистика:\n✅ {correct_count} | ❌ {wrong_count}")

        # --- НОВЫЙ ВОПРОС ---
        word, choices, correct = generate_question(user_id, mode)
        user_data[user_id] = {"correct": correct, "mode": mode}

        if mode == "trainer":
            text = f"{word['he']} — {word['tr']}\nВыберите правильный перевод:"
        else:
            text = f"{word['he']}\nВыберите правильный вариант:"

        await call.message.answer(text, reply_markup=build_keyboard(choices, include_reset=True))

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
