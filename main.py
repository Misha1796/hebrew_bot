import asyncio
import random
import os
import json
import edge_tts
from google import genai
from google.genai import types
from aiogram import Bot, Dispatcher, types as tg_types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")

# Инициализация нового клиента
client = genai.Client(api_key=GEMINI_KEY)

# Список моделей для проверки (от новой к стабильной)
MODEL_VARIANTS = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-2.0-flash-exp"]

def get_best_model():
    """Функция автоматического подбора рабочей модели"""
    for m_id in MODEL_VARIANTS:
        try:
            client.models.generate_content(model=m_id, contents="test", config=types.GenerateContentConfig(max_output_tokens=1))
            print(f"✅ Успешно подключена модель: {m_id}")
            return m_id
        except Exception as e:
            print(f"⚠️ Модель {m_id} недоступна: {e}")
    return "gemini-1.5-flash" # Дефолт, если всё упало

ACTIVE_MODEL = get_best_model()

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

# Маппинг категорий (твои пропавшие пункты теперь здесь)
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
        [InlineKeyboardButton(text="🎙 Голосовой AI", callback_data="go_ai_chat")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_trainer_categories():
    buttons = []
    # Автоматически создаем кнопки для ВСЕХ ключей в words.json
    for key in words_data.keys():
        name = CAT_NAMES.get(key, key.capitalize())
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"mode_{key}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ЛОГИКА ИИ ---

@dp.callback_query(F.data == "go_translator")
async def start_translator(call: tg_types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.translator)
    await call.message.edit_text("✍️ **Режим переводчика**\nНапиши фразу на русском.", 
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Выход", callback_data="to_main")]]), 
                               parse_mode="Markdown")

@dp.message(BotStates.translator)
async def handle_translation(message: tg_types.Message):
    if message.text and message.text.startswith('/'): return
    try:
        response = client.models.generate_content(
            model=ACTIVE_MODEL,
            contents=f"Переведи на иврит: '{message.text}'. Дай перевод, транскрипцию и род.",
            config=types.GenerateContentConfig(
                system_instruction="Ты эксперт по ивриту. Твои ответы коротки и точны."
            )
        )
        await message.answer(response.text, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)[:100]}...")

@dp.callback_query(F.data == "go_ai_chat")
async def start_ai_chat(call: tg_types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.ai_chat)
    await call.message.edit_text("🎙 **Голосовой AI**\nПришли голосовое сообщение!", 
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Выход", callback_data="to_main")]]), 
                               parse_mode="Markdown")

@dp.message(BotStates.ai_chat, F.voice)
async def handle_ai_voice(message: tg_types.Message):
    file_id = message.voice.file_id
    input_p, output_p = f"{file_id}.ogg", f"res_{file_id}.mp3"
    await bot.download_file((await bot.get_file(file_id)).file_path, input_p)
    try:
        # Загрузка файла в Gemini
        with open(input_p, "rb") as f:
            uploaded_file = client.files.upload(file=f, config={'mime_type': 'audio/ogg'})
            
        response = client.models.generate_content(
            model=ACTIVE_MODEL,
            contents=[uploaded_file, "Ответь кратко на языке пользователя."]
        )
        
        comm = edge_tts.Communicate(response.text, "he-IL-AvriNeural")
        await comm.save(output_p)
        await message.answer_voice(voice=FSInputFile(output_p))
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)[:50]}")
    finally:
        for p in [input_p, output_p]:
            if os.path.exists(p): os.remove(p)

# --- ТРЕНАЖЕР ---

async def send_question(message, user_id, mode, feedback=""):
    if user_id not in user_states or user_states[user_id].get("mode") != mode:
        user_states[user_id] = {"mode": mode, "learned": []}
    st = user_states[user_id]
    source = revision_data.get("revision", []) if mode == "revision" else words_data.get(mode, [])
    
    available = [w for w in source if w["ru"] not in st["learned"]]
    if not available:
        await message.edit_text(f"{feedback}\n\n🎉 Раздел пройден!", reply_markup=get_main_menu(), parse_mode="Markdown")
        return

    item = random.choice(available)
    st["current_item"] = item
    all_ru = [w["ru"] for w in source]
    choices = list(set([item["ru"]] + random.sample(all_ru, min(len(all_ru), 4))))
    random.shuffle(choices)
    st["current_choices"] = choices
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c, callback_data=f"ans_{i}")] for i, c in enumerate(choices)] + [[InlineKeyboardButton(text="🔙 Меню", callback_data="to_main")]])
    text = f"{feedback}\n" if feedback else ""
    text += f"Как переводится?\n\n🇮🇱 **{item['he']}**"
    await message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(call: tg_types.CallbackQuery):
    user_id = call.from_user.id
    st = user_states.get(user_id)
    if not st: return
    ans = st["current_choices"][int(call.data.replace("ans_", ""))]
    item = st["current_item"]
    if ans == item["ru"]:
        st["learned"].append(item["ru"])
        fb = "✅ Верно!"
    else:
        fb = f"❌ Ошибка! Это: {item['ru']}"
    await send_question(call.message, user_id, st["mode"], feedback=fb)

@dp.callback_query(F.data.startswith("mode_"))
async def select_mode(call: tg_types.CallbackQuery):
    await send_question(call.message, call.from_user.id, call.data.split("_")[1])

@dp.message(Command("start"))
async def cmd_start(message: tg_types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🇮🇱 Привет! Я готов к работе. Выбери раздел:", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "to_main")
async def go_to_main(call: tg_types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🏠 Главное меню", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "trainer_menu")
async def trainer_menu(call: tg_types.CallbackQuery):
    await call.message.edit_text("📖 Категории:", reply_markup=get_trainer_categories(), parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
