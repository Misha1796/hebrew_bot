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

# --- ЖЕСТКИЙ ФИКС ВЕРСИИ API ---
os.environ["GOOGLE_GENERATIVE_AI_API_VERSION"] = "v1"

# Настройки из Railway
TOKEN = os.getenv("TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")

# --- ИНИЦИАЛИЗАЦИЯ GEMINI ---
genai.configure(api_key=GEMINI_KEY, transport="rest")

# Используем максимально стабильную версию модели
model = genai.GenerativeModel(
    model_name='models/gemini-1.5-flash',
    system_instruction="Ты — профессиональный учитель иврита. Твоя задача — переводить фразы с русского на иврит, обязательно указывать транскрипцию русскими буквами и пояснять род (мужской/женский)."
)

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

# Красивые названия для кнопок
CAT_NAMES = {
    "verbs": "🎬 Глаголы", "phrases": "💬 Фразы", "nouns": "🏠 Существительные",
    "adjectives": "🎨 Прилагательные", "connectors": "🔗 Связки",
    "past": "🔙 Прошлое", "future": "🔜 Будущее"
}

# --- КЛАВИАТУРЫ ---

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton(text="📖 Тренажёр слов", callback_data="trainer_menu")],
        [InlineKeyboardButton(text="🔄 Повторение", callback_data="mode_revision")],
        [InlineKeyboardButton(text="📚 Теория", callback_data="theory_main")],
        [InlineKeyboardButton(text="🇮🇱 Переводчик", callback_data="go_translator")],
        [InlineKeyboardButton(text="🎙 Голосовой AI", callback_data="go_ai_chat")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_trainer_categories():
    buttons = []
    # Автоматически создаем кнопки из всех ключей в words.json
    for key in words_data.keys():
        name = CAT_NAMES.get(key, key.capitalize())
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"mode_{key}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_quiz_kb(choices):
    btns = [[InlineKeyboardButton(text=c, callback_data=f"ans_{i}")] for i, c in enumerate(choices)]
    btns.append([InlineKeyboardButton(text="🔙 Меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=btns)

# --- ЛОГИКА ИИ ---

@dp.callback_query(F.data == "go_translator")
async def start_translator(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.translator)
    await call.message.edit_text("✍️ **Режим переводчика**\nНапиши фразу на русском, и я переведу её.", 
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Выход", callback_data="to_main")]]), 
                               parse_mode="Markdown")

@dp.message(BotStates.translator)
async def handle_translation(message: types.Message):
    if message.text and message.text.startswith('/'): return
    try:
        # Прямой запрос к модели
        response = model.generate_content(f"Переведи: {message.text}")
        await message.answer(response.text, parse_mode="Markdown")
    except Exception as e:
        await message.answer("⚠️ ИИ временно недоступен. Попробуй позже.")
        print(f"Ошибка Gemini: {e}")

@dp.callback_query(F.data == "go_ai_chat")
async def start_ai_chat(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.ai_chat)
    await call.message.edit_text("🎙 **Голосовой AI**\nПришли голосовое сообщение на русском или иврите!", 
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Выход", callback_data="to_main")]]), 
                               parse_mode="Markdown")

@dp.message(BotStates.ai_chat, F.voice)
async def handle_ai_voice(message: types.Message):
    file_id = message.voice.file_id
    input_p, output_p = f"{file_id}.ogg", f"res_{file_id}.mp3"
    await bot.download_file((await bot.get_file(file_id)).file_path, input_p)
    try:
        audio_file = genai.upload_file(path=input_p, mime_type="audio/ogg")
        response = model.generate_content([audio_file, "Ответь кратко на языке пользователя."])
        
        comm = edge_tts.Communicate(response.text, "he-IL-AvriNeural")
        await comm.save(output_p)
        await message.answer_voice(voice=FSInputFile(output_p))
    except Exception as e:
        await message.answer("⚠️ Ошибка обработки голоса.")
    finally:
        for p in [input_p, output_p]:
            if os.path.exists(p): os.remove(p)

# --- ЛОГИКА ТРЕНАЖЕРА ---

@dp.callback_query(F.data == "trainer_menu")
async def show_trainer_menu(call: types.CallbackQuery):
    await call.message.edit_text("📖 **Выберите раздел для тренировки:**", reply_markup=get_trainer_categories(), parse_mode="Markdown")

async def send_question(message, user_id, mode, feedback=""):
    if user_id not in user_states or user_states[user_id].get("mode") != mode:
        user_states[user_id] = {"mode": mode, "current_item": {}, "learned": [], "current_choices": []}
    
    st = user_states[user_id]
    source = revision_data.get("revision", []) if mode == "revision" else words_data.get(mode, [])
    
    available = [w for w in source if w["ru"] not in st["learned"]]
    if not available:
        await message.edit_text(f"{feedback}\n\n🎉 Раздел полностью пройден!", 
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 В меню", callback_data="to_main")]]), 
                               parse_mode="Markdown")
        return

    item = random.choice(available)
    st["current_item"] = item
    all_ru = [w["ru"] for w in source]
    choices = list(set([item["ru"]] + random.sample(all_ru, min(len(all_ru), 4))))
    random.shuffle(choices)
    st["current_choices"] = choices
    
    text = f"{feedback}\n" if feedback else ""
    text += f"Как переводится?\n\n🇮🇱 **{item['he']}**"
    if "tr" in item: text += f"\n*({item['tr']})*"
    
    await message.edit_text(text, reply_markup=get_quiz_kb(choices), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(call: types.CallbackQuery):
    user_id = call.from_user.id
    st = user_states.get(user_id)
    if not st: return

    ans = st["current_choices"][int(call.data.replace("ans_", ""))]
    item = st["current_item"]
    if user_id not in user_stats: user_stats[user_id] = {"correct": 0, "wrong": 0}

    if ans == item["ru"]:
        user_stats[user_id]["correct"] += 1
        st["learned"].append(item["ru"])
        fb = "✅ **Верно!**"
    else:
        user_stats[user_id]["wrong"] += 1
        fb = f"❌ **Ошибка!** Правильно: `{item['ru']}`"

    await send_question(call.message, user_id, st["mode"], feedback=fb)
    await call.answer()

@dp.callback_query(F.data.startswith("mode_"))
async def select_mode(call: types.CallbackQuery):
    await send_question(call.message, call.from_user.id, call.data.split("_")[1])

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🇮🇱 **Шалом!** Я твой бот для изучения иврита.\nВыбери нужный раздел:", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "to_main")
async def go_to_main(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🏠 **Главное меню**", reply_markup=get_main_menu(), parse_mode="Markdown")

# --- СТАТИСТИКА И ТЕОРИЯ ---
@dp.callback_query(F.data == "theory_main")
async def theory_menu(call: types.CallbackQuery):
    btns = [[InlineKeyboardButton(text=k.capitalize(), callback_data=f"th_{k}")] for k in theory_data.keys()]
    btns.append([InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")])
    await call.message.edit_text("📚 **Выберите тему:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("th_"))
async def show_theory(call: types.CallbackQuery):
    key = call.data.replace("th_", "")
    await call.message.edit_text(f"📘 {theory_data.get(key, '...')}", 
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="theory_main")]]), 
                               parse_mode="Markdown")

@dp.callback_query(F.data == "stats_main")
async def show_stats(call: types.CallbackQuery):
    s = user_stats.get(call.from_user.id, {"correct": 0, "wrong": 0})
    await call.message.edit_text(f"📊 **Твои успехи:**\n\n✅ Верно: `{s['correct']}`\n❌ Ошибок: `{s['wrong']}`", 
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")]]), 
                               parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
