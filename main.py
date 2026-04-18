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
theory_file = "theory.json"
revision_file = "revision.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ПЕРЕВОДЧИК ТЕМ (из английских ключей в русские названия) ---
THEORY_TITLES = {
    "alphabet": "🅰️ Алфавит",
    "nekudot": "📍 Огласовки",
    "article": "🆔 Артикль",
    "gender": "👫 Род",
    "plural": "🔢 Мн. число",
    "et": "🎯 Частица ЭТ",
    "binyanim": "🏗 Биньяны",
    "past_ya": "🔙 Прошлое (Я)",
    "future_ya": "🔜 Будущее (Я)",
    "present": "🕒 Настоящее время",
    "object": "👤 Меня/Его",
    "prepositions": "📍 Предлоги",
    "negation": "🚫 Отрицание",
    "questions": "❓ Вопросы",
    "yesh_ein": "💎 Есть/Нет",
    "letter_h": "🌬 Буква hей",
    "stress": "⚡ Ударение"
}

# --- ЗАГРУЗКА ДАННЫХ ---
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

words_data = load_json(words_file)
theory_data = load_json(theory_file)
revision_data = load_json(revision_file)

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
        [InlineKeyboardButton(text="🔄 Повторение слов", callback_data="mode_revision")],
        [InlineKeyboardButton(text="📚 Теория", callback_data="theory_main")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_quiz_kb(choices):
    # Используем индекс i вместо текста, чтобы избежать BUTTON_DATA_INVALID
    buttons = [[InlineKeyboardButton(text=c, callback_data=f"ans_{i}")] for i, c in enumerate(choices)]
    buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ЛОГИКА ВОПРОСОВ ---

async def send_question(message, user_id, mode, feedback=""):
    if user_id not in user_states or user_states[user_id].get("mode") != mode:
        user_states[user_id] = {"mode": mode, "current_item": {}, "learned": [], "current_choices": []}
    
    state = user_states[user_id]
    source = revision_data.get("revision", []) if mode == "revision" else words_data.get(mode, [])
    
    if not source:
        await message.answer("⚠️ Список слов пуст.")
        return

    available_words = [w for w in source if w["ru"] not in state["learned"]]
    
    if not available_words:
        text = f"{feedback}\n\n🎉 **Раздел пройден!**"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Заново", callback_data="stats_reset")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="to_main")]
        ])
        await message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    item = random.choice(available_words)
    state["current_item"] = item
    
    # Генерируем варианты ответов
    correct = item["ru"]
    all_variants = [w["ru"] for w in source]
    choices = list(set([correct] + random.sample(all_variants, min(len(all_variants), 4))))
    random.shuffle(choices)
    
    # Сохраняем текущие варианты в состояние пользователя, чтобы потом проверить по индексу
    state["current_choices"] = choices
    
    stats = user_stats.get(user_id, {"correct": 0, "wrong": 0})
    tr = f" — *{item['tr']}*" if "tr" in item else ""
    
    text = f"{feedback}\n" if feedback else ""
    text += f"📈 {stats['correct']} | Осталось: {len(available_words)}\n"
    text += "────────────────────\n"
    text += f"Как переводится?\n\n🇮🇱 **{item['he']}**{tr}"
    
    try:
        await message.edit_text(text, reply_markup=get_quiz_kb(choices), parse_mode="Markdown")
    except:
        await message.answer(text, reply_markup=get_quiz_kb(choices), parse_mode="Markdown")

# --- ОБРАБОТЧИКИ ТЕОРИИ ---

@dp.callback_query(F.data == "theory_main")
async def theory_menu(call: types.CallbackQuery):
    if not theory_data:
        await call.answer("Файл теории пуст", show_alert=True)
        return
    buttons = []
    for key in theory_data.keys():
        title = THEORY_TITLES.get(key, key.capitalize())
        buttons.append([InlineKeyboardButton(text=title, callback_data=f"th_{key}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")])
    await call.message.edit_text("📚 **Выберите тему:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("th_"))
async def show_theory_content(call: types.CallbackQuery):
    topic_key = call.data.replace("th_", "")
    content = theory_data.get(topic_key, "Текст не найден.")
    title = THEORY_TITLES.get(topic_key, topic_key.capitalize())
    text = f"📘 **{title}**\n\n{content}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку", callback_data="theory_main")]])
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except:
        await call.message.edit_text(text, reply_markup=kb, parse_mode=None)
    await call.answer()

# --- ОБРАБОТКА ОТВЕТОВ ---

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(call: types.CallbackQuery):
    user_id = call.from_user.id
    choice_index = int(call.data.replace("ans_", ""))
    state = user_states.get(user_id)
    
    if not state or "current_choices" not in state:
        await call.answer("Ошибка состояния. Попробуйте /start")
        return

    ans = state["current_choices"][choice_index]
    correct_item = state["current_item"]
    
    if user_id not in user_stats: 
        user_stats[user_id] = {"correct": 0, "wrong": 0}

    if ans == correct_item["ru"]:
        user_stats[user_id]["correct"] += 1
        state["learned"].append(correct_item["ru"])
        feedback = "✅ **Верно!**"
    else:
        user_stats[user_id]["wrong"] += 1
        tr = f"({correct_item['tr']})" if "tr" in correct_item else ""
        feedback = f"❌ **Ошибка!**\nВерно: `{correct_item['ru']}` {tr}"

    await send_question(call.message, user_id, state["mode"], feedback=feedback)
    await call.answer()

# --- ОБЩИЕ КОМАНДЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🇮🇱 **Шалом!** Выбери раздел:", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "to_main")
async def go_to_main(call: types.CallbackQuery):
    await call.message.edit_text("🏠 **Главное меню**", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("mode_"))
async def select_mode(call: types.CallbackQuery):
    mode = call.data.split("_")[1]
    user_states[call.from_user.id] = {"mode": mode, "current_item": {}, "learned": [], "current_choices": []}
    await send_question(call.message, call.from_user.id, mode)

@dp.callback_query(F.data == "stats_main")
async def show_stats(call: types.CallbackQuery):
    stats = user_stats.get(call.from_user.id, {"correct": 0, "wrong": 0})
    text = f"📊 **Статистика**\n\n✅ Верно: `{stats['correct']}`\n❌ Ошибок: `{stats['wrong']}`"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Сброс", callback_data="stats_reset")], [InlineKeyboardButton(text="🏠 Меню", callback_data="to_main")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "stats_reset")
async def reset_stats(call: types.CallbackQuery):
    user_id = call.from_user.id
    user_stats[user_id] = {"correct": 0, "wrong": 0}
    if user_id in user_states: user_states[user_id]["learned"] = []
    await call.answer("Прогресс сброшен")
    await go_to_main(call)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
