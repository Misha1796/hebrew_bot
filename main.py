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

user_states = {} 
user_stats = {}

# --- КЛАВИАТУРЫ ---

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton(text="📖 Тренажёр слов", callback_data="mode_trainer")],
        [InlineKeyboardButton(text="⏳ Будущее время", callback_data="mode_future")],
        [InlineKeyboardButton(text="📜 Прошедшее время", callback_data="mode_past")],
        [InlineKeyboardButton(text="🎨 Прилагательные", callback_data="mode_adjectives")],
        [InlineKeyboardButton(text="🔗 Связующие слова", callback_data="mode_connectors")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_quiz_kb(choices):
    # Каждая кнопка на всю ширину
    buttons = [[InlineKeyboardButton(text=c, callback_data=f"ans_{c}")] for c in choices]
    buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ЛОГИКА ВОПРОСОВ ---

async def send_question(message, user_id, mode, feedback=""):
    if user_id not in user_states:
        user_states[user_id] = {"mode": mode, "current_item": {}, "wrong_words": []}
    
    state = user_states[user_id]
    
    # Умный повтор
    if state["wrong_words"]:
        item = state["wrong_words"].pop(0)
    else:
        item = random.choice(words_data[mode])
    
    state["current_item"] = item
    correct = item["ru"]
    
    # Варианты ответов
    all_variants = [w["ru"] for w in words_data[mode]]
    choices = list(set([correct] + random.sample(all_variants, min(len(all_variants), 4))))
    random.shuffle(choices)
    
    # Статистика для отображения в тексте
    stats = user_stats.get(user_id, {"correct": 0, "wrong": 0})
    header_stats = f"📈 {stats['correct']} | 📉 {stats['wrong']}"
    
    # Формирование текста
    transcription = f"*{item['tr']}*" if "tr" in item else ""
    
    # Красивое оформление сообщения
    text = ""
    if feedback:
        text += f"{feedback}\n"
        text += "────────────────────\n"
    
    text += f"{header_stats}\n\n"
    text += f"Как переводится слово?\n"
    text += f"💎 **{item['he']}** {transcription}"
    
    # Используем edit_text, если это ответ на вопрос, или answer, если это начало
    try:
        await message.edit_text(text, reply_markup=get_quiz_kb(choices), parse_mode="Markdown")
    except:
        await message.answer(text, reply_markup=get_quiz_kb(choices), parse_mode="Markdown")

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = (
        "✨ **Добро пожаловать в Иврит-Бот!** ✨\n\n"
        "Выбери режим обучения ниже, чтобы начать тренировку."
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "to_main")
async def go_to_main(call: types.CallbackQuery):
    await call.message.edit_text("🏠 **Главное меню**\nВыбери режим обучения:", 
                               reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("mode_"))
async def select_mode(call: types.CallbackQuery):
    mode = call.data.split("_")[1]
    user_id = call.from_user.id
    user_states[user_id] = {"mode": mode, "current_item": {}, "wrong_words": []}
    await send_question(call.message, user_id, mode)

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(call: types.CallbackQuery):
    user_id = call.from_user.id
    ans = call.data.replace("ans_", "")
    state = user_states.get(user_id)
    
    if not state: 
        await go_to_main(call)
        return

    correct_item = state["current_item"]
    if user_id not in user_stats:
        user_stats[user_id] = {"correct": 0, "wrong": 0}

    # Формируем фидбек вместо всплывающего окна
    if ans == correct_item["ru"]:
        user_stats[user_id]["correct"] += 1
        feedback = "✅ **Верно!**"
    else:
        user_stats[user_id]["wrong"] += 1
        for _ in range(3):
            state["wrong_words"].append(correct_item)
        tr_info = f"({correct_item['tr']})" if "tr" in correct_item else ""
        feedback = f"❌ **Ошибка!**\nПравильно: `{correct_item['ru']}` {tr_info}"

    # Сразу отправляем следующий вопрос, передавая фидбек
    await send_question(call.message, user_id, state["mode"], feedback=feedback)
    await call.answer() # Просто подтверждаем клик, без текста

@dp.callback_query(F.data == "stats_main")
async def show_stats(call: types.CallbackQuery):
    stats = user_stats.get(call.from_user.id, {"correct": 0, "wrong": 0})
    text = (
        "📊 **Твоя личная статистика**\n"
        "────────────────────\n"
        f"✅ Правильных ответов: `{stats['correct']}`\n"
        f"❌ Допущено ошибок: `{stats['wrong']}`\n"
        "────────────────────\n"
        "Продолжай в том же духе!"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Сбросить прогресс", callback_data="stats_reset")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="to_main")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "stats_reset")
async def reset_stats(call: types.CallbackQuery):
    user_id = call.from_user.id
    user_stats[user_id] = {"correct": 0, "wrong": 0}
    if user_id in user_states:
        user_states[user_id]["wrong_words"] = []
    await call.answer("Прогресс обнулен")
    await go_to_main(call)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
