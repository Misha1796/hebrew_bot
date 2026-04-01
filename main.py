import asyncio
import random
import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- ТОКЕН ---
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ЗАГРУЗКА СЛОВ ИЗ JSON ---
words_file = "words.json"
if not os.path.exists(words_file):
    # пример структуры
    sample_words = {
        "trainer": [
            {"he": "לעשות", "tr": "лаасот", "ru": "делать"},
            {"he": "לאכול", "tr": "леэхоль", "ru": "есть"},
            {"he": "לשתות", "tr": "лиштот", "ru": "пить"},
            {"he": "לישון", "tr": "лишон", "ru": "спать"}
        ],
        "future": [
            {"he": "אעשה", "ru": "сделаю"},
            {"he": "אוכל", "ru": "поем"},
        ],
        "past": [
            {"he": "עשיתי", "ru": "сделал"},
            {"he": "אכלתי", "ru": "съел"},
        ],
        "adjectives": [
            {"he": "גדול", "tr": "гадоль", "ru": "большой"},
            {"he": "קטן", "tr": "катан", "ru": "маленький"}
        ],
        "connectors": [
            {"he": "אבל", "tr": "аваль", "ru": "но"},
            {"he": "או", "tr": "о", "ru": "или"}
        ]
    }
    with open(words_file, "w", encoding="utf-8") as f:
        json.dump(sample_words, f, ensure_ascii=False, indent=4)

with open(words_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# --- ДАННЫЕ ПОЛЬЗОВАТЕЛЕЙ ---
user_data = {}  # {user_id: {"correct": "ответ", "mode": "trainer", "wrong_words": []}}
user_stats = {}  # {user_id: {"correct": int, "wrong": int}}

# --- МЕНЮ ---
def main_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1️⃣ Тренажёр слов", callback_data="mode_trainer")],
            [InlineKeyboardButton(text="2️⃣ Будущее время", callback_data="mode_future")],
            [InlineKeyboardButton(text="3️⃣ Прошедшее время", callback_data="mode_past")],
            [InlineKeyboardButton(text="4️⃣ Прилагательные", callback_data="mode_adjectives")],
            [InlineKeyboardButton(text="5️⃣ Связующие слова", callback_data="mode_connectors")]
        ]
    )
    return keyboard

# --- КНОПКИ ВОПРОСОВ ---
def build_keyboard(choices, include_reset=False):
    buttons = [InlineKeyboardButton(text=f"{c}⠀", callback_data=c) for c in choices]  # добавляем невидимый символ для размера
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    if include_reset:
        rows.append([InlineKeyboardButton(text="🔄 Сбросить статистику", callback_data="reset")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# --- СТАТИСТИКА ---
def update_stats(user_id, is_correct, word=None):
    if user_id not in user_stats:
        user_stats[user_id] = {"correct": 0, "wrong": 0}
    if is_correct:
        user_stats[user_id]["correct"] += 1
    else:
        user_stats[user_id]["wrong"] += 1
        # добавляем слово в повтор
        if user_id not in user_data:
            user_data[user_id] = {"wrong_words": []}
        user_data[user_id].setdefault("wrong_words", []).extend([word]*5)  # повтор 5 раз

def get_stats(user_id):
    if user_id not in user_stats:
        user_stats[user_id] = {"correct": 0, "wrong": 0}
    return user_stats[user_id]["correct"], user_stats[user_id]["wrong"]

def reset_stats(user_id):
    user_stats[user_id] = {"correct": 0, "wrong": 0}
    if user_id in user_data:
        user_data[user_id]["wrong_words"] = []

# --- ГЕНЕРАЦИЯ ВОПРОСА ---
def generate_question(user_id, mode="trainer"):
    # проверка на повтор ошибок
    wrong_words = user_data.get(user_id, {}).get("wrong_words", [])
    if wrong_words:
        item = wrong_words.pop(0)
    else:
        item = random.choice(data[mode])
    correct = item["ru"]
    # для кнопок используем все остальные слова этого режима
    all_options = [w["ru"] for w in data[mode] if w["ru"] != correct]
    if len(all_options) < 3:
        choices = all_options + [correct]*(3 - len(all_options))
    else:
        choices = random.sample(all_options, 3)
        choices.append(correct)
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
    if call.data.startswith("mode_"):
        mode = call.data.replace("mode_", "")
        user_data[user_id] = {"mode": mode, "wrong_words": []}
        item, choices, correct = generate_question(user_id, mode)
        user_data[user_id]["correct"] = correct
        # текст вопроса
        if mode in ["trainer", "adjectives", "connectors"]:
            text = f"{item['he']} — {item.get('tr', '')}\nВыберите правильный перевод:"
        else:  # будущие/прошедшие время
            text = f"{item['he']}\nВыберите правильный перевод:"
        await call.message.answer(text, reply_markup=build_keyboard(choices, include_reset=True))
        await call.answer()

# --- ОТВЕТ НА ВОПРОС ---
@dp.callback_query(lambda c: c.data != "reset" and not c.data.startswith("mode_"))
async def answer(call: types.CallbackQuery):
    user_id = call.from_user.id
    correct = user_data[user_id]["correct"]
    mode = user_data[user_id]["mode"]
    # проверка ответа
    if call.data == correct:
        update_stats(user_id, True)
        result_text = f"✅ Верно! {user_data[user_id]['correct']}"
    else:
        update_stats(user_id, False, word=correct)
        result_text = f"❌ Неверно! Правильный ответ: {user_data[user_id]['correct']}"
    correct_count, wrong_count = get_stats(user_id)
    await call.message.edit_text(f"{result_text}\n\n📊 Статистика:\n✅ {correct_count} | ❌ {wrong_count}")
    # следующий вопрос
    item, choices, correct = generate_question(user_id, mode)
    user_data[user_id]["correct"] = correct
    # текст вопроса
    if mode in ["trainer", "adjectives", "connectors"]:
        text = f"{item['he']} — {item.get('tr', '')}\nВыберите правильный перевод:"
    else:
        text = f"{item['he']}\nВыберите правильный перевод:"
    await call.message.answer(text, reply_markup=build_keyboard(choices, include_reset=True))
    await call.answer()

# --- СБРОС СТАТИСТИКИ ---
@dp.callback_query(lambda c: c.data == "reset")
async def reset(call: types.CallbackQuery):
    user_id = call.from_user.id
    reset_stats(user_id)
    await call.message.edit_text("📊 Статистика обнулена!")
    await call.message.answer("📚 Главное меню", reply_markup=main_menu())
    await call.answer()

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
