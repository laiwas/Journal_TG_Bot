import asyncio
import os
import tempfile
import datetime
from typing import Dict, Any

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv

from stt import ogg_to_wav, transcribe
from llm import structure_day  # без missing_questions

# ──────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("В .env не найден TELEGRAM_BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

SESSION: Dict[int, Dict[str, Any]] = {}  # chat_id -> {"mode": "journal"|"task", "last": dict}

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
        input_field_placeholder="Выбери режим или просто пришли текст/голос"
    )

def render_summary(date_str: str, d: Dict[str, Any]) -> str:
    ap = d.get("ActionPoints") or {}
    return (
        f"Сводка за {date_str}:\n\n"
        f"Дела и мысли:\n- " + "\n- ".join(d.get("DayLog", []) or ["—"]) + "\n\n"
        f"Чувства: {d.get('Feelings') or '—'}\n\n"
        f"Три победы:\n- " + "\n- ".join(d.get("ThreeWins", []) or ["—"]) + "\n\n"
        f"StoryWorthy:\n{d.get('StoryWorthy') or '—'}\n\n"
        f"СДВГ: {d.get('ADHDScore', 0)}\n\n"
        f"Action Points:\n"
        f"- Книга: {'Да' if ap.get('BookRead') else 'Нет'}\n"
        f"- Записи: {'Да' if ap.get('NotesDone') else 'Нет'}\n"
        f"- RPG: {'Да' if ap.get('RPG') else 'Нет'}\n"
        f"- Finance: {'Да' if ap.get('Finance') else 'Нет'}"
    )

# ──────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────
@dp.message(CommandStart())
async def start(m: Message):
    SESSION[m.chat.id] = {"mode": "journal", "last": {}}
    await m.answer(
        "Привет! Выбери режим на клавиатуре ниже.\n\n"
        "• Daily Journal — разложу день по секциям (без уточняющих вопросов).\n"
        "• Понимание задачи — заглушка (подключим позже).",
        reply_markup=kb_main()
    )

@dp.message(Command("newday"))
async def newday(m: Message):
    SESSION[m.chat.id] = {"mode": "journal", "last": {}}
    await m.answer("Новый день. Пришли текст или голос — соберу сводку.", reply_markup=kb_main())

@dp.message(Command("summary"))
async def summary_cmd(m: Message):
    s = SESSION.get(m.chat.id) or {}
    d = s.get("last") or {}
    if not d:
        return await m.answer("Пока нет данных. Пришли текст или голос в режиме Daily Journal.", reply_markup=kb_main())
    await m.answer(render_summary(today_iso(), d)[:4000], reply_markup=kb_main())

# ──────────────────────────────────────────────
# Mode switches (buttons)
# ──────────────────────────────────────────────
@dp.message(F.text.lower() == "daily journal")
async def choose_journal(m: Message):
    SESSION[m.chat.id] = {"mode": "journal", "last": SESSION.get(m.chat.id, {}).get("last", {})}
    await m.answer("Режим: Daily Journal. Опиши день текстом или голосом.", reply_markup=kb_main())

@dp.message(F.text.lower() == "понимание задачи")
async def choose_task(m: Message):
    SESSION[m.chat.id] = {"mode": "task", "last": SESSION.get(m.chat.id, {}).get("last", {})}
    await m.answer(
        "Режим: Понимание задачи (заглушка).\n"
        "Пришли голос/текст — пока просто верну расшифровку/эхо.\n"
        "Позже здесь будет анализ и формулировка задачи.",
        reply_markup=kb_main()
    )

# ──────────────────────────────────────────────
# Core processors
# ──────────────────────────────────────────────
async def process_journal(m: Message, raw_text: str):
    """Без уточняющих вопросов: что прислал — то и структурируем"""
    data = structure_day(raw_text)
    SESSION[m.chat.id]["last"] = data
    await m.answer(render_summary(today_iso(), data)[:4000], reply_markup=kb_main())

async def process_task_stub(m: Message, raw_text: str):
    """Заглушка режима 'Понимание задачи'"""
    await m.answer("Заглушка режима 'Понимание задачи'.\nВот что я получил:\n\n" + raw_text[:3500], reply_markup=kb_main())

# ──────────────────────────────────────────────
# Text & Voice handlers
# ──────────────────────────────────────────────
@dp.message(F.text & ~F.via_bot)
async def handle_text(m: Message):
    s = SESSION.setdefault(m.chat.id, {"mode": "journal", "last": {}})
    mode = s.get("mode", "journal")
    text = (m.text or "").strip()
    if not text:
        return await m.answer("Похоже, пусто. Напиши пару фраз или пришли голос.", reply_markup=kb_main())

    if mode == "journal":
        await process_journal(m, text)
    else:
        await process_task_stub(m, text)

@dp.message(F.voice | F.audio)
async def handle_audio(m: Message):
    # скачать файл
    tg_file = await bot.get_file(m.voice.file_id if m.voice else m.audio.file_id)
    ogg_path = tempfile.mktemp(suffix=".ogg")
    await bot.download_file(tg_file.file_path, destination=ogg_path)

    try:
        wav_path = ogg_to_wav(ogg_path)
        text = transcribe(wav_path)  # рус. язык зафиксирован в stt.py
    except Exception as e:
        return await m.answer(f"Не удалось распознать аудио: {e}", reply_markup=kb_main())

    if not text:
        return await m.answer("Не распознал речь. Попробуй ещё раз.", reply_markup=kb_main())

    s = SESSION.setdefault(m.chat.id, {"mode": "journal", "last": {}})
    mode = s.get("mode", "journal")
    if mode == "journal":
        await process_journal(m, text)
    else:
        await process_task_stub(m, text)

# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
async def main():
    print("Bot is running… Ctrl+C для остановки")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())