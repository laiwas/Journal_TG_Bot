# bot.py — две кнопки режимов, без уточняющих вопросов.
# Daily Journal: структурирование дня (вывод в формате для Notion)
# Понимание задачи: STT/текст -> промпт на понимание задачи

import asyncio
import os
import tempfile
import datetime
from typing import Dict, Any

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv

# ВАЖНО: модуль stt должен уметь распознавать голос.
# Рекомендуемый интерфейс (совместим со старым кодом):
#   ogg_to_wav(path) -> str
#   transcribe(wav_path) -> str  # внутри может дергать OpenAI Whisper API
from stt import ogg_to_wav, transcribe

# Модуль llm должен иметь:
#   structure_day(text) -> str   # возвращает ГОТОВЫЙ текст для Notion (с триггером "История:")
#   understand_task(text) -> str # формирует карточку задачи по твоему промпту
from llm import structure_day, understand_task


# ──────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("В .env не найден TELEGRAM_BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# chat_id -> {"mode": "journal"|"task", "last_text": str}
SESSION: Dict[int, Dict[str, Any]] = {}


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def today_iso() -> str:
    return datetime.date.today().isoformat()

def kb_main() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Daily Journal")],
            [KeyboardButton(text="Понимание задачи")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выбери режим или пришли текст/голос"
    )

def render_notion(text: str) -> str:
    """Возвращаем подготовленный текст как есть (отрезаем Telegram лимит)."""
    return (text or "").strip()[:4000]


# ──────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────
@dp.message(CommandStart())
async def start(m: Message):
    SESSION[m.chat.id] = {"mode": "journal", "last_text": ""}
    await m.answer(
        "Привет! Выбери режим на клавиатуре ниже.\n\n"
        "• Daily Journal — разложу день по секциям (готовый текст для Notion, без уточняющих вопросов).\n"
        "• Понимание задачи — пришли текст/голос с описанием задачи, оформлю карточку задачи.",
        reply_markup=kb_main()
    )

@dp.message(Command("newday"))
async def newday(m: Message):
    SESSION[m.chat.id] = {"mode": "journal", "last_text": ""}
    await m.answer("Новый день. Пришли текст или голос — соберу сводку (формат для Notion).", reply_markup=kb_main())

@dp.message(Command("summary"))
async def summary_cmd(m: Message):
    s = SESSION.get(m.chat.id) or {}
    last_text = s.get("last_text", "")
    if not last_text:
        return await m.answer("Пока нет данных. Пришли текст или голос в режиме Daily Journal.", reply_markup=kb_main())
    await m.answer(render_notion(last_text), reply_markup=kb_main())

@dp.message(Command("help"))
async def help_cmd(m: Message):
    await m.answer(
        "Команды:\n"
        "/start — выбор режима\n"
        "/newday — начать новый день (очистить предыдущую сводку)\n"
        "/summary — показать последнюю сводку\n\n"
        "Режимы:\n"
        "• Daily Journal — пришли голос или текст. Если в голосе есть эпизод для истории, скажи «История: …» — этот фрагмент попадёт в раздел StoryWorthy & Observations.\n"
        "• Понимание задачи — пришли голос/текст, оформлю по шаблону.\n",
        reply_markup=kb_main()
    )


# ──────────────────────────────────────────────
# Mode switches (buttons)
# ──────────────────────────────────────────────
@dp.message(F.text.lower() == "daily journal")
async def choose_journal(m: Message):
    SESSION[m.chat.id] = {
        "mode": "journal",
        "last_text": SESSION.get(m.chat.id, {}).get("last_text", "")
    }
    await m.answer("Режим: Daily Journal. Опиши день текстом или голосом.", reply_markup=kb_main())

@dp.message(F.text.lower() == "понимание задачи")
async def choose_task(m: Message):
    SESSION[m.chat.id] = {
        "mode": "task",
        "last_text": SESSION.get(m.chat.id, {}).get("last_text", "")
    }
    await m.answer(
        "Режим: Понимание задачи. Пришли голос/текст с описанием задачи — оформлю по структуре.",
        reply_markup=kb_main()
    )


# ──────────────────────────────────────────────
# Core processors
# ──────────────────────────────────────────────
async def process_journal(m: Message, raw_text: str):
    """
    Ожидается, что llm.structure_day вернёт уже ГОТОВЫЙ текст
    строго в формате для Notion (хедеры, списки, объединённый блок StoryWorthy & Observations).
    Логика с триггером «История: …» зашита в промпт внутри llm.py.
    """
    try:
        notion_text = structure_day(raw_text)  # <- должен вернуть str
    except Exception as e:
        return await m.answer(f"Ошибка при формировании дневника: {e}", reply_markup=kb_main())

    SESSION[m.chat.id]["last_text"] = notion_text
    await m.answer(render_notion(notion_text), reply_markup=kb_main())

async def process_task(m: Message, raw_text: str):
    try:
        task_text = understand_task(raw_text)  # <- текстовая карточка задачи по твоему промпу
    except Exception as e:
        return await m.answer(f"Ошибка при разборе задачи: {e}", reply_markup=kb_main())

    await m.answer(task_text[:4000], reply_markup=kb_main())


# ──────────────────────────────────────────────
# Text & Voice handlers
# ──────────────────────────────────────────────
@dp.message(F.text & ~F.via_bot)
async def handle_text(m: Message):
    s = SESSION.setdefault(m.chat.id, {"mode": "journal", "last_text": ""})
    mode = s.get("mode", "journal")
    text = (m.text or "").strip()
    if not text:
        return await m.answer("Похоже, пусто. Напиши пару фраз или пришли голос.", reply_markup=kb_main())

    if mode == "journal":
        await process_journal(m, text)
    else:
        await process_task(m, text)

@dp.message(F.voice | F.audio)
async def handle_audio(m: Message):
    # скачать файл
    try:
        tg_file = await bot.get_file(m.voice.file_id if m.voice else m.audio.file_id)
        ogg_path = tempfile.mktemp(suffix=".ogg")
        await bot.download_file(tg_file.file_path, destination=ogg_path)
    except Exception as e:
        return await m.answer(f"Не удалось скачать аудио: {e}", reply_markup=kb_main())

    # STT
    try:
        wav_path = ogg_to_wav(ogg_path)      # если в твоём stt это уже не нужно — можешь внутри no-op сделать
        text = transcribe(wav_path)          # внутри можно дергать OpenAI Whisper API с language='ru'
    except Exception as e:
        return await m.answer(f"Не удалось распознать аудио: {e}", reply_markup=kb_main())

    if not text:
        return await m.answer("Не распознал речь. Попробуй ещё раз.", reply_markup=kb_main())

    s = SESSION.setdefault(m.chat.id, {"mode": "journal", "last_text": ""})
    mode = s.get("mode", "journal")
    if mode == "journal":
        await process_journal(m, text)
    else:
        await process_task(m, text)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
async def main():
    print("Bot is running… Ctrl+C для остановки")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
