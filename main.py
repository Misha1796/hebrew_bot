import asyncio
import random
import os
import json
from openai import AsyncOpenAI  # Используем новую библиотеку OpenAI
import edge_tts
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Инициализация клиента OpenAI
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

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

MENU_TITLES = {
    "verbs": "🎬 Глаголы", "phrases": "💬 Фразы", "nouns": "🏠 Существительные",
    "adjectives": "🎨 Прилагательные", "connectors": "🔗 Связки",
    "past": "🔙 Прошлое время", "future": "🔜 Будущее время"
}

# --- ЛОГИКА ИИ (OpenAI GPT-4o-mini) ---

@dp.callback_query(F.data == "go_translator")
async def start_translator(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.translator)
    await call.message.edit_text("✍️ **Режим переводчика (GPT)**\nНапиши фразу на русском.", 
                               reply_markup=get_back_kb(), parse_mode="Markdown")

@dp.message(BotStates.translator)
async def handle_translation(message: types.Message):
    if message.text and message.text.startswith('/'): return
    try:
        # Запрос к GPT
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты эксперт по ивриту. Переводи фразы, давай транскрипцию и указывай род."},
                {"role": "user", "content": f"Переведи на иврит: {message.text}"}
            ]
        )
        await message.answer(response.choices[0].message.content, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка OpenAI: {str(e)}")

@dp.callback_query(F.data == "go_ai_chat")
async def start_ai_chat(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.ai_chat)
    await call.message.edit_text("🎙 **Голосовой AI**\nПришли голосовое сообщение!", reply_markup=get_back_kb(), parse_mode="Markdown")

@dp.message(BotStates.ai_chat, F.voice)
async def handle_ai_voice(message: types.Message):
    # Для обработки голоса в OpenAI нужно сначала перевести аудио в текст (Whisper)
    file_id = message.voice.file_id
    input_path = f"{file_id}.ogg"
    output_path = f"res_{file_id}.mp3"
    
    await bot.download_file((await bot.get_file(file_id)).file_path, input_path)
    
    try:
        # 1. Транскрипция аудио через Whisper
        with open(input_path, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        
        # 2. Ответ от GPT
        gpt_res = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": transcript.text}]
        )
        answer_text = gpt_res.choices[0].message.content
        
        # 3. Озвучка ответа
        communicate = edge_tts.Communicate(answer_text, "he-IL-AvriNeural")
        await communicate.save(output_path)
        
        await message.answer_voice(voice=FSInputFile(output_path))
    except Exception as e:
        await message.answer(f"⚠️ Ошибка голоса: {str(e)}")
    finally:
        for p in [input_path, output_path]:
            if os.path.exists(p): os.remove(p)

# --- ВСЁ ОСТАЛЬНОЕ (Тренажер и меню) ---

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

def get_trainer_categories():
    buttons = []
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

@dp.callback_query(F.data == "trainer_menu")
async def show_trainer_menu(call: types.CallbackQuery):
    await call.message.edit_text("📖 **Выберите категорию:**", reply_markup=get_trainer_categories(), parse_mode="Markdown")

async def send_question(message, user_id, mode, feedback=""):
    if user_id not in user_states or user_states[user_id].get("mode") != mode:
        user_states[user_id] = {"mode": mode, "current_item": {}, "learned": [], "current_choices": []}
    state = user_states[user_id]
    source = revision_data.get("revision", []) if mode == "revision" else words_data.get(mode, [])
    if not source: return
    available = [w for w in source if w["ru"] not in state["learned"]]
    if not available:
        await message.edit_text(f"{feedback}\n\n🎉 Готово!", reply_markup=get_back_kb(), parse_mode="Markdown")
        return
    item = random.choice(available)
    state["current_item"] = item
    all_ru = [w["ru"] for w in source]
    choices = list(set([item["ru"]] + random.sample(all_ru, min(len(all_ru), 4))))
    random.shuffle(choices)
    state["current_choices"] = choices
    text = f"{feedback}\n" if feedback else ""
    text += f"Как переводится?\n\n🇮🇱 **{item['he']}**"
    await message.edit_text(text, reply_markup=get_quiz_kb(choices), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(call: types.CallbackQuery):
    user_id = call.from_user.id
    state = user_states.get(user_id)
    if not state: return
    ans = state["current_choices"][int(call.data.replace("ans_", ""))]
    correct_item = state["current_item"]
    if ans == correct_item["ru"]:
        state["learned"].append(correct_item["ru"])
        feedback = "✅ Верно!"
    else:
        feedback = f"❌ Ошибка! Это: {correct_item['ru']}"
    await send_question(call.message, user_id, state["mode"], feedback=feedback)
    await call.answer()

@dp.callback_query(F.data.startswith("mode_"))
async def select_mode(call: types.CallbackQuery):
    await send_question(call.message, call.from_user.id, call.data.split("_")[1])

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🇮🇱 Привет! Выбери раздел:", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "to_main")
async def go_to_main(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🏠 Главное меню", reply_markup=get_main_menu(), parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
