import asyncio
import random
import os
import json
import edge_tts
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Инициализация Groq
client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

TEXT_MODEL = "llama-3.3-70b-versatile"
AUDIO_MODEL = "whisper-large-v3"

bot = Bot(token=TOKEN)
dp = Dispatcher()

class BotStates(StatesGroup):
    translator = State()
    ai_chat = State()

# --- ПЕРЕВОДЧИК ТЕМ ---
THEORY_TITLES = {
    "alphabet": "🅰️ Алфавит", "nekudot": "📍 Огласовки", "article": "🆔 Артикль",
    "gender": "👫 Род", "plural": "🔢 Мн. число", "et": "🎯 Частица ЭТ",
    "binyanim": "🏗 Биньяны", "past_ya": "🔙 Прошлое (Я)", "future_ya": "🔜 Будущее (Я)",
    "present": "🕒 Настоящее время", "object": "👤 Меня/Его", "prepositions": "📍 Предлоги",
    "negation": "🚫 Отрицание", "questions": "❓ Вопросы", "yesh_ein": "💎 Есть/Нет",
    "letter_h": "🌬 Буква hей", "stress": "⚡ Ударение"
}

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

# --- КЛАВИАТУРЫ ---

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton(text="📖 Тренажёр слов", callback_data="trainer_menu")],
        [InlineKeyboardButton(text="🔄 Повторение", callback_data="mode_revision")],
        [InlineKeyboardButton(text="📚 Теория", callback_data="theory_main")],
        [InlineKeyboardButton(text="🇮🇱 Переводчик (AI)", callback_data="go_translator")],
        [InlineKeyboardButton(text="🎙 Голосовой AI", callback_data="go_ai_chat")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_trainer_categories():
    buttons = []
    # Категории на основе ключей в words.json
    for key in words_data.keys():
        name = key.capitalize()
        if key == "past": name = "🔙 Прошлое"
        elif key == "future": name = "🔜 Будущее"
        elif key == "adjectives": name = "🎨 Прилагательные"
        elif key == "connectors": name = "🔗 Связки"
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"mode_{key}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_quiz_kb(choices):
    buttons = [[InlineKeyboardButton(text=c, callback_data=f"ans_{i}")] for i, c in enumerate(choices)]
    buttons.append([InlineKeyboardButton(text="🔙 Меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ЛОГИКА ТРЕНАЖЕРА ---

async def send_question(message, user_id, mode, feedback=""):
    if user_id not in user_states or user_states[user_id].get("mode") != mode:
        user_states[user_id] = {"mode": mode, "current_item": {}, "learned": [], "current_choices": []}
    
    st = user_states[user_id]
    source = revision_data.get("revision", []) if mode == "revision" else words_data.get(mode, [])
    
    if not source:
        await message.answer("⚠️ Список слов пуст.")
        return

    available = [w for w in source if w["ru"] not in st["learned"]]
    if not available:
        text = f"{feedback}\n\n🎉 **Раздел пройден!**"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Заново", callback_data="stats_reset")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="to_main")]
        ])
        await message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    item = random.choice(available)
    st["current_item"] = item
    all_ru = [w["ru"] for w in source]
    choices = list(set([item["ru"]] + random.sample(all_ru, min(len(all_ru), 4))))
    random.shuffle(choices)
    st["current_choices"] = choices
    
    stats = user_stats.get(user_id, {"correct": 0, "wrong": 0})
    tr = f" — *{item['tr']}*" if "tr" in item else ""
    
    text = f"{feedback}\n" if feedback else ""
    text += f"📈 Верно: {stats['correct']} | Осталось: {len(available)}\n"
    text += "────────────────────\n"
    text += f"Как переводится?\n\n🇮🇱 **{item['he']}**{tr}"
    
    await message.edit_text(text, reply_markup=get_quiz_kb(choices), parse_mode="Markdown")

# --- ОБРАБОТЧИКИ ---

@dp.callback_query(F.data == "trainer_menu")
async def show_trainer_menu(call: types.CallbackQuery):
    await call.message.edit_text("📖 **Выберите категорию:**", reply_markup=get_trainer_categories(), parse_mode="Markdown")

@dp.callback_query(F.data == "theory_main")
async def theory_menu(call: types.CallbackQuery):
    buttons = [[InlineKeyboardButton(text=THEORY_TITLES.get(k, k.capitalize()), callback_data=f"th_{k}")] for k in theory_data.keys()]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")])
    await call.message.edit_text("📚 **Темы теории:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("th_"))
async def show_theory_content(call: types.CallbackQuery):
    key = call.data.replace("th_", "")
    content = theory_data.get(key, "Текст не найден.")
    title = THEORY_TITLES.get(key, key.capitalize())
    await call.message.edit_text(f"📘 **{title}**\n\n{content}", 
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку", callback_data="theory_main")]]), 
                               parse_mode="Markdown")

@dp.callback_query(F.data == "stats_main")
async def show_stats(call: types.CallbackQuery):
    stats = user_stats.get(call.from_user.id, {"correct": 0, "wrong": 0})
    text = f"📊 **Твоя статистика**\n\n✅ Правильно: `{stats['correct']}`\n❌ Ошибок: `{stats['wrong']}`"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Сброс", callback_data="stats_reset")], [InlineKeyboardButton(text="🏠 Меню", callback_data="to_main")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "stats_reset")
async def reset_stats(call: types.CallbackQuery):
    user_id = call.from_user.id
    user_stats[user_id] = {"correct": 0, "wrong": 0}
    if user_id in user_states: user_states[user_id]["learned"] = []
    await call.answer("Прогресс обнулен")
    await go_to_main(call)

# --- ИИ ЛОГИКА (GROQ) ---

@dp.callback_query(F.data == "go_translator")
async def start_translator(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.translator)
    await call.message.edit_text("✍️ **Переводчик (Llama 3.3)**\nНапиши фразу для перевода:", 
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")]]), 
                               parse_mode="Markdown")

@dp.message(BotStates.translator)
async def handle_translation(message: types.Message):
    if message.text and message.text.startswith('/'): return
    try:
        res = await client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{"role": "system", "content": "Ты учитель иврита. Переводи, давай транскрипцию и род."},
                      {"role": "user", "content": message.text}]
        )
        await message.answer(res.choices[0].message.content, parse_mode="Markdown")
    except Exception as e:
        await message.answer("⚠️ Ошибка AI. Проверь API ключ Groq.")

@dp.callback_query(F.data == "go_ai_chat")
async def start_ai_chat(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.ai_chat)
    await call.message.edit_text("🎙 **Голосовой AI**\nПришли голосовое сообщение!", 
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")]]), 
                               parse_mode="Markdown")

@dp.message(BotStates.ai_chat, F.voice)
async def handle_ai_voice(message: types.Message):
    file_id = message.voice.file_id
    # Оставляем расширение .ogg, так как Telegram присылает именно его
    input_p = f"{file_id}.ogg"
    output_p = f"res_{file_id}.mp3"
    
    # Скачиваем файл
    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, input_p)
    
    try:
        # 1. Распознавание (Whisper)
        # Важно: передаем кортеж (имя_файла, бинарные_данные)
        with open(input_p, "rb") as f:
            audio_data = f.read()
            
        transcription = await client.audio.transcriptions.create(
            model=AUDIO_MODEL,
            file=(input_p, audio_data), # Передаем имя файла для корректного определения формата
            response_format="text"
        )
        
        if not transcription.strip():
            await message.answer("🤖 Я не разобрал слова в голосовом сообщении.")
            return

        # 2. Ответ от Llama
        response = await client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "system", "content": "Ты эксперт по ивриту. Отвечай кратко на языке пользователя."},
                {"role": "user", "content": transcription}
            ]
        )
        
        reply_text = response.choices[0].message.content

        # 3. Озвучка (Edge-TTS)
        comm = edge_tts.Communicate(reply_text, "he-IL-AvriNeural")
        await comm.save(output_p)
        
        await message.answer_voice(
            voice=FSInputFile(output_p),
            caption=f"📝 {reply_text[:100]}..." # Добавим текст ответа в описание
        )

    except Exception as e:
        # Выводим полную ошибку для диагностики
        print(f"Ошибка Voice: {e}")
        await message.answer(f"⚠️ Ошибка голосового чата: {str(e)[:100]}")
    finally:
        # Чистим за собой
        for p in [input_p, output_p]:
            if os.path.exists(p):
                try: os.remove(p)
                except: pass
# --- СИСТЕМНЫЕ ОБРАБОТЧИКИ ---

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
        fb = f"❌ **Ошибка!**\nПравильно: `{item['ru']}`"

    await send_question(call.message, user_id, st["mode"], feedback=fb)
    await call.answer()

@dp.callback_query(F.data.startswith("mode_"))
async def select_mode(call: types.CallbackQuery):
    mode = call.data.split("_")[1]
    await send_question(call.message, call.from_user.id, mode)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🇮🇱 **Шалом!** Выбери режим обучения:", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "to_main")
async def go_to_main(call: types.CallbackQuery, state: FSMContext = None):
    if state: await state.clear()
    await call.message.edit_text("🏠 **Главное меню**", reply_markup=get_main_menu(), parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
