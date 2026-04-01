import asyncio
import random
import os
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("TOKEN")
words_file = "words.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ЗАГРУЗКА ДАННЫХ ---
def load_words():
    if os.path.exists(words_file):
        with open(words_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

words_data = load_words()

# Временное хранилище (сбросится при перезагрузке на Railway)
user_states = {} # {user_id: {"mode": str, "current_item": dict, "wrong_words": []}}
user_stats = {}  # {user_id: {"correct": int, "wrong": int}}

# --- КЛАВИАТУРЫ ---

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton(text="1️⃣ Тренажёр слов", callback_data="mode_trainer")],
        [InlineKeyboardButton(text="2️⃣ Будущее время", callback_data="mode_future")],
        [InlineKeyboardButton(text="3️⃣ Прошедшее время", callback_data="mode_past")],
        [InlineKeyboardButton(text="4️⃣ Прилагательные", callback_data="mode_adjectives")],
        [InlineKeyboardButton(text="5️⃣ Связующие слова", callback_data="mode_connectors")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_quiz_kb(choices):
    # Каждая кнопка на новой строке = правильная ширина
    buttons = [[InlineKeyboardButton(text=c, callback_data=f"ans_{c}")] for c in choices]
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ЛОГИКА ВОПРОСОВ ---

async def send_question(message, user_id, mode):
    if user_id not in user_states:
        user_states[user_id] = {"mode": mode, "current_item": {}, "wrong_words": []}
    
    state = user_states[user_id]
    
    # Умный повтор: если есть ошибки в очереди, берем их
    if state["wrong_words"]:
        item = state["wrong_words"].pop(0)
    else:
        item = random.choice(words_data[mode])
    
    state["current_item"] = item
    correct = item["ru"]
    
    # Генерируем варианты ответов (правильный + 3 случайных)
    all_variants = [w["ru"] for w in words_data[mode]]
    choices = [correct]
    other_variants = list(set(all_variants) - {correct})
    
    if len(other_variants) >= 3:
        choices.extend(random.sample(other_variants, 3))
    else:
        choices.extend(other_variants)
    
    random.shuffle(choices)
    
    # Формируем текст (Иврит + Транскрипция если есть)
    transcription = f"({item['tr']})" if "tr" in item else ""
    text = f"Как переводится:\n\n🇮🇱 **{item['he']}** {transcription}"
    
    await message.answer(text, reply_markup=get_quiz_kb(choices), parse_mode="Markdown")

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Выбери режим обучения:", reply_markup=get_main_menu())

@dp.callback_query(F.data == "to_main")
async def go_to_main(call: types.CallbackQuery):
    await call.message.edit_text("Выбери режим обучения:", reply_markup=get_main_menu())

@dp.callback_query(F.data.startswith("mode_"))
async def select_mode(call: types.CallbackQuery):
    mode = call.data.split("_")[1]
    user_id = call.from_user.id
    
    if user_id not in user_states:
        user_states[user_id] = {"mode": mode, "current_item": {}, "wrong_words": []}
    else:
        user_states[user_id]["mode"] = mode
        
    await call.message.delete()
    await send_question(call.message, user_id, mode)

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(call: types.CallbackQuery):
    user_id = call.from_user.id
    ans = call.data.replace("ans_", "")
    
    state = user_states.get(user_id)
    if not state: return

    correct_item = state["current_item"]
    
    if user_id not in user_stats:
        user_stats[user_id] = {"correct": 0, "wrong": 0}

    if ans == correct_item["ru"]:
        user_stats[user_id]["correct"] += 1
        feedback = "✅ Верно!"
    else:
        user_stats[user_id]["wrong"] += 1
        # Умный повтор: добавляем слово в очередь 3 раза
        for _ in range(3):
            state["wrong_words"].append(correct_item)
        feedback = f"❌ Ошибка!\nПравильно: {correct_item['ru']}"

    await call.answer(feedback, show_alert=True)
    await call.message.delete()
    await send_question(call.message, user_id, state["mode"])

@dp.callback_query(F.data == "stats_main")
async def show_stats(call: types.CallbackQuery):
    stats = user_stats.get(call.from_user.id, {"correct": 0, "wrong": 0})
    text = f"📊 Твои успехи:\n\n✅ Правильно: {stats['correct']}\n❌ Ошибок: {stats['wrong']}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Сбросить статистику", callback_data="stats_reset")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="to_main")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "stats_reset")
async def reset_stats(call: types.CallbackQuery):
    user_id = call.from_user.id
    user_stats[user_id] = {"correct": 0, "wrong": 0}
    if user_id in user_states:
        user_states[user_id]["wrong_words"] = []
    await call.answer("Статистика обнулена!")
    await go_to_main(call)

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
