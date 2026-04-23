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

# --- ФИКС ОШИБКИ 404 ---
# Принудительно устанавливаем стабильную версию API v1
os.environ["GOOGLE_GENERATIVE_AI_API_VERSION"] = "v1"

TOKEN = os.getenv("TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")

# Настройка Gemini
genai.configure(api_key=GEMINI_KEY)
# Используем прямое имя модели без префиксов
model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Состояния для переключения режимов
class BotStates(StatesGroup):
    translator = State()
    ai_chat = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return {}
    return {}

words_data = load_json("words.json")
theory_data = load_json("theory.json")
revision_data = load_json("revision.json")

# --- КЛАВИАТУРЫ ---
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton(text="📖 Тренажёр слов", callback_data="mode_trainer")],
        [InlineKeyboardButton(text="🔄 Повторение", callback_data="mode_revision")],
        [InlineKeyboardButton(text="📚 Теория", callback_data="theory_main")],
        [InlineKeyboardButton(text="🇮🇱 Как это сказать?", callback_data="go_translator")],
        [InlineKeyboardButton(text="🎙 Голосовой AI", callback_data="go_ai_chat")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В меню", callback_data="to_main")]])

# --- ЛОГИКА ПЕРЕВОДЧИКА ---
@dp.callback_query(F.data == "go_translator")
async def start_translator(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.translator)
    await call.message.edit_text("✍️ **Режим переводчика**\nНапиши фразу на русском, и я переведу её на иврит с транскрипцией.", reply_markup=get_back_kb(), parse_mode="Markdown")

@dp.message(BotStates.translator)
async def handle_translation(message: types.Message):
    if message.text and message.text.startswith('/'): return
    
    prompt = f"Ты эксперт по ивриту. Переведи: '{message.text}'. Дай: 1. Перевод 2. Транскрипцию 3. Разницу м/ж рода."
    try:
        response = model.generate_content(prompt)
        await message.answer(response.text, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка ИИ: {str(e)}")

# --- ЛОГИКА ГОЛОСОВОГО AI ---
@dp.callback_query(F.data == "go_ai_chat")
async def start_ai_chat(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.ai_chat)
    await call.message.edit_text("🎙 **Голосовой AI**\nПришли голосовое сообщение, и я отвечу тебе голосом!", reply_markup=get_back_kb(), parse_mode="Markdown")

@dp.message(BotStates.ai_chat, F.voice)
async def handle_ai_voice(message: types.Message):
    file_id = message.voice.file_id
    input_path = f"{file_id}.ogg"
    output_path = f"res_{file_id}.mp3"
    
    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, input_path)

    try:
        # mime_type важен для корректной работы с ogg
        raw_audio = genai.upload_file(path=input_path, mime_type="audio/ogg")
        response = model.generate_content([raw_audio, "Ответь кратко на иврите или русском."])
        
        # Генерация голоса через edge-tts
        communicate = edge_tts.Communicate(response.text, "he-IL-AvriNeural")
        await communicate.save(output_path)
        
        await message.answer_voice(voice=FSInputFile(output_path))
    except Exception as e:
        await message.answer(f"⚠️ Ошибка обработки: {str(e)}")
    finally:
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

# --- УПРАВЛЕНИЕ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear() # Сбрасываем все режимы ИИ при старте
    await message.answer("🇮🇱 **Шалом!** Выбери раздел:", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "to_main")
async def go_to_main(call: types.CallbackQuery, state: FSMContext):
    await state.clear() # Сбрасываем режимы ИИ при возврате в меню
    await call.message.edit_text("🏠 **Главное меню**", reply_markup=get_main_menu(), parse_mode="Markdown")

async def main():
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
