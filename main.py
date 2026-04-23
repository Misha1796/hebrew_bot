import asyncio
import random
import os
import json
import google.generativeai as genai
import edge_tts
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# --- ЖЕСТКИЙ ФИКС API ---
os.environ["GOOGLE_GENERATIVE_AI_API_VERSION"] = "v1"

genai.configure(api_key=GEMINI_KEY, transport="rest") # Используем REST вместо gRPC для стабильности

def get_ultra_stable_model():
    # Мы пробуем только стабильные имена
    for name in ["gemini-1.5-flash", "gemini-pro"]:
        try:
            # Явно указываем версию API при создании модели через параметр
            m = genai.GenerativeModel(
                model_name=f"models/{name}"
            )
            # Тестовый мирок-запрос
            m.generate_content("Hi", generation_config={"max_output_tokens": 1})
            print(f"✅ Успешно: {name}")
            return m
        except Exception as e:
            print(f"❌ {name} мимо: {e}")
    return None

model = get_ultra_stable_model()

bot = Bot(token=TOKEN)
dp = Dispatcher()

class BotStates(StatesGroup):
    translator = State()
    ai_chat = State()

# --- ЗАГРУЗКА ДАННЫХ ---
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return {}
    return {}

words_data = load_json("words.json")
theory_data = load_json("theory.json")
revision_data = load_json("revision.json")

user_states = {} 
user_stats = {}

# Словарь названий для меню (добавлены твои пропавшие пункты)
MENU_TITLES = {
    "verbs": "🎬 Глаголы",
    "phrases": "💬 Фразы",
    "nouns": "🏠 Существительные",
    "adjectives": "🎨 Прилагательные",
    "connectors": "🔗 Связки",
    "past": "🔙 Прошлое время",
    "future": "🔜 Будущее время"
}

THEORY_TITLES = {
    "alphabet": "🅰️ Алфавит", "nekudot": "📍 Огласовки", "article": "🆔 Артикль",
    "gender": "👫 Род", "plural": "🔢 Мн. число", "et": "🎯 Частица ЭТ",
    "binyanim": "🏗 Биньяны", "past_ya": "🔙 Прошлое (Я)", "future_ya": "🔜 Будущее (Я)",
    "present": "🕒 Настоящее время", "object": "👤 Меня/Его", "prepositions": "📍 Предлоги",
    "negation": "🚫 Отрицание", "questions": "❓ Вопросы", "yesh_ein": "💎 Есть/Нет",
    "letter_h": "🌬 Буква hей", "stress": "⚡ Ударение"
}

# --- КЛАВИАТУРЫ ---

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton(text="📖 Тренажёр слов", callback_data="trainer_menu")],
        [InlineKeyboardButton(text="🔄 Повторение", callback_data="mode_revision")],
        [InlineKeyboardButton(text="📚 Теория", callback_data="theory_main")],
        [InlineKeyboardButton(text="🇮🇱 Как это сказать?", callback_data="go_translator")],
        [InlineKeyboardButton(text="🎙 Голосовой AI", callback_data="go_ai_chat")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Специальное меню для выбора категории слов (чтобы ничего не пропадало)
def get_trainer_categories():
    buttons = []
    # Автоматически создаем кнопки на основе ключей в words.json
    for key in words_data.keys():
        title = MENU_TITLES.get(key, key.capitalize())
        buttons.append([InlineKeyboardButton(text=title, callback_data=f"mode_{key}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_quiz_kb(choices):
    buttons = [[InlineKeyboardButton(text=c, callback_data=f"ans_{i}")] for i, c in enumerate(choices)]
    buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В главное меню", callback_data="to_main")]])

# --- ЛОГИКА ИИ ---

@dp.callback_query(F.data == "go_translator")
async def start_translator(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.translator)
    await call.message.edit_text("✍️ **Режим переводчика**\nНапиши фразу на русском, и я переведу её на иврит.", reply_markup=get_back_kb(), parse_mode="Markdown")

@dp.message(BotStates.translator)
async def handle_translation(message: types.Message):
    if message.text and message.text.startswith('/'): return
    try:
        prompt = f"Переведи на иврит: '{message.text}'. Дай: перевод, транскрипцию русскими буквами и род (м/ж)."
        response = model.generate_content(prompt)
        await message.answer(response.text, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка ИИ: {str(e)}")

@dp.message(BotStates.ai_chat, F.voice)
async def handle_ai_voice(message: types.Message):
    file_id = message.voice.file_id
    input_path = f"{file_id}.ogg"
    output_path = f"res_{file_id}.mp3"
    await bot.download_file((await bot.get_file(file_id)).file_path, input_path)
    try:
        raw_audio = genai.upload_file(path=input_path, mime_type="audio/ogg")
        response = model.generate_content([raw_audio, "Ответь очень кратко (до 15 слов) на иврите или русском."])
        communicate = edge_tts.Communicate(response.text, "he-IL-AvriNeural")
        await communicate.save(output_path)
        await message.answer_voice(voice=FSInputFile(output_path))
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")
    finally:
        for p in [input_path, output_path]:
            if os.path.exists(p): os.remove(p)

@dp.callback_query(F.data == "go_ai_chat")
async def start_ai_chat(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.ai_chat)
    await call.message.edit_text("🎙 **Голосовой AI**\nПришли голосовое сообщение, и я отвечу тебе голосом!", reply_markup=get_back_kb(), parse_mode="Markdown")

# --- ЛОГИКА ТРЕНАЖЕРА ---

@dp.callback_query(F.data == "trainer_menu")
async def show_trainer_menu(call: types.CallbackQuery):
    await call.message.edit_text("📖 **Выберите категорию для изучения:**", reply_markup=get_trainer_categories(), parse_mode="Markdown")

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
        await message.edit_text(text, reply_markup=get_back_kb(), parse_mode="Markdown")
        return

    item = random.choice(available_words)
    state["current_item"] = item
    all_variants = [w["ru"] for w in source]
    choices = list(set([item["ru"]] + random.sample(all_variants, min(len(all_variants), 4))))
    random.shuffle(choices)
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

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(call: types.CallbackQuery):
    user_id = call.from_user.id
    state = user_states.get(user_id)
    if not state: return

    ans = state["current_choices"][int(call.data.replace("ans_", ""))]
    correct_item = state["current_item"]
    if user_id not in user_stats: user_stats[user_id] = {"correct": 0, "wrong": 0}

    if ans == correct_item["ru"]:
        user_stats[user_id]["correct"] += 1
        state["learned"].append(correct_item["ru"])
        feedback = "✅ **Верно!**"
    else:
        user_stats[user_id]["wrong"] += 1
        feedback = f"❌ **Ошибка!** Верно: `{correct_item['ru']}`"

    await send_question(call.message, user_id, state["mode"], feedback=feedback)
    await call.answer()

@dp.callback_query(F.data.startswith("mode_"))
async def select_mode(call: types.CallbackQuery):
    mode = call.data.split("_")[1]
    await send_question(call.message, call.from_user.id, mode)

@dp.callback_query(F.data == "theory_main")
async def theory_menu(call: types.CallbackQuery):
    buttons = []
    for key in theory_data.keys():
        title = THEORY_TITLES.get(key, key.capitalize())
        buttons.append([InlineKeyboardButton(text=title, callback_data=f"th_{key}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")])
    await call.message.edit_text("📚 **Выберите тему:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("th_"))
async def show_theory_content(call: types.CallbackQuery):
    topic_key = call.data.replace("th_", "")
    text = f"📘 **{THEORY_TITLES.get(topic_key, topic_key)}**\n\n{theory_data.get(topic_key, '...')}"
    await call.message.edit_text(text, reply_markup=get_back_kb(), parse_mode="Markdown")

@dp.callback_query(F.data == "stats_main")
async def show_stats(call: types.CallbackQuery):
    stats = user_stats.get(call.from_user.id, {"correct": 0, "wrong": 0})
    await call.message.edit_text(f"📊 **Статистика**\n\n✅ Верно: `{stats['correct']}`\n❌ Ошибок: `{stats['wrong']}`", reply_markup=get_back_kb(), parse_mode="Markdown")

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🇮🇱 **Шалом!** Выбери раздел:", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "to_main")
async def go_to_main(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🏠 **Главное меню**", reply_markup=get_main_menu(), parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
