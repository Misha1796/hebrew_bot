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

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")

# Настройка Gemini (используем обновленный вызов модели)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash-latest")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Состояния FSM
class BotStates(StatesGroup):
    translator = State()
    ai_chat = State()

# --- ЗАГРУЗКА ДАННЫХ ---
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

words_data = load_json("words.json")
theory_data = load_json("theory.json")
revision_data = load_json("revision.json")

# Словари для работы тренажера
THEORY_TITLES = {
    "alphabet": "🅰️ Алфавит", "nekudot": "📍 Огласовки", "article": "🆔 Артикль",
    "gender": "👫 Род", "plural": "🔢 Мн. число", "et": "🎯 Частица ЭТ",
    "binyanim": "🏗 Биньяны", "past_ya": "🔙 Прошлое (Я)", "future_ya": "🔜 Будущее (Я)",
    "present": "🕒 Настоящее время", "object": "👤 Меня/Его", "prepositions": "📍 Предлоги",
    "negation": "🚫 Отрицание", "questions": "❓ Вопросы", "yesh_ein": "💎 Есть/Нет",
    "letter_h": "🌬 Буква hей", "stress": "⚡ Ударение"
}

user_states = {} 
user_stats = {}

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

def get_quiz_kb(choices):
    buttons = [[InlineKeyboardButton(text=c, callback_data=f"ans_{i}")] for i, c in enumerate(choices)]
    buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В главное меню", callback_data="to_main")]])

# --- ЛОГИКА ИИ (НОВОЕ) ---

@dp.callback_query(F.data == "go_translator")
async def start_translator(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.translator)
    await call.message.edit_text("✍️ **Режим переводчика**\nНапиши фразу на русском, и я переведу её на иврит с транскрипцией.", reply_markup=get_back_kb(), parse_mode="Markdown")

@dp.message(BotStates.translator)
async def handle_translation(message: types.Message):
    prompt = f"Ты помощник по ивриту. Переведи на иврит: '{message.text}'. Напиши: 1. Перевод. 2. Транскрипцию русскими буквами. 3. Если есть разница в роде, укажи м.р. и ж.р."
    try:
        response = model.generate_content(prompt)
        await message.answer(response.text, parse_mode="Markdown")
    except Exception as e:
        # Теперь бот пришлет саму ошибку, а не просто текст про ключ
        await message.answer(f"⚠️ Ошибка ИИ: {str(e)}")

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
        # Исправляем ошибку mime_type из логов
        raw_audio = genai.upload_file(path=input_path, mime_type="audio/ogg")
        response = model.generate_content([raw_audio, "Ответь кратко на иврите или русском, до 20 слов."])
        
        # Озвучка через Edge-TTS
        communicate = edge_tts.Communicate(response.text, "he-IL-AvriNeural")
        await communicate.save(output_path)
        
        await message.answer_voice(voice=FSInputFile(output_path))
    except Exception as e:
        await message.answer(f"⚠️ Ошибка обработки: {str(e)}")
    finally:
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

# --- ЛОГИКА ТРЕНАЖЕРА (Твой оригинальный код) ---

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
    correct = item["ru"]
    all_variants = [w["ru"] for w in source]
    choices = list(set([correct] + random.sample(all_variants, min(len(all_variants), 4))))
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
    choice_index = int(call.data.replace("ans_", ""))
    state = user_states.get(user_id)
    if not state or "current_choices" not in state: return

    ans = state["current_choices"][choice_index]
    correct_item = state["current_item"]
    if user_id not in user_stats: user_stats[user_id] = {"correct": 0, "wrong": 0}

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

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🇮🇱 **Шалом!** Выбери раздел:", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "to_main")
async def go_to_main(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🏠 **Главное меню**", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("mode_"))
async def select_mode(call: types.CallbackQuery):
    mode = call.data.split("_")[1]
    user_states[call.from_user.id] = {"mode": mode, "current_item": {}, "learned": [], "current_choices": []}
    await send_question(call.message, call.from_user.id, mode)

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
