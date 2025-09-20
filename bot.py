import asyncio
import os
import tempfile
import datetime
from typing import Dict, Any

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv

from stt import ogg_to_wav, transcribe
from llm import structure_day, missing_questions

# ──────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("В .env не найден TELEGRAM_BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

SESSION: Dict[int, Dict[str, Any]] = {}

def today_iso() -> str:
    return datetime.date.today().isoformat()

NEG_WORDS = {"нет", "не было", "no", "-", "неа", "нету"}

def field_from_question(q: str) -> str | None:
    q = (q or "").lower()
    if "истори" in q or "момент" in q: return "StoryWorthy"
    if "дела" in q and "мысли" in q: return "DayLog"
    if "чувств" in q: return "Feelings"
    if "3 побед" in q or "три побед" in q: return "ThreeWins"
    if "сдвг" in q or "adhd" in q: return "ADHDScore"
    return None

def yes_no(v: bool) -> str:
    return "Да" if bool(v) else "Нет"

def _render_summary(date_str: str, d: Dict[str, Any]) -> str:
    ap = d.get("ActionPoints") or {}
    return (
        f"Сводка за {date_str}:\n\n"
        f"Дела и мысли:\n- " + "\n- ".join(d.get("DayLog", []) or ["—"]) + "\n\n"
        f"Чувства: {d.get('Feelings') or '—'}\n\n"
        f"Три победы:\n- " + "\n- ".join(d.get("ThreeWins", []) or ["—"]) + "\n\n"
        f"StoryWorthy: {d.get('StoryWorthy') or '—'}\n\n"
        f"СДВГ: {d.get('ADHDScore', 0)}\n\n"
        f"Action Points:\n"
        f"- Книга: {yes_no(ap.get('BookRead'))}\n"
        f"- Записи: {yes_no(ap.get('NotesDone'))}\n"
        f"- RPG: {yes_no(ap.get('RPG'))}\n"
        f"- Finance: {yes_no(ap.get('Finance'))}"
    )

# ──────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────
@dp.message(CommandStart())
async def start(m: Message):
    await m.answer(
        "Привет! Пришли текст или голосовое — соберу день по секциям:\n"
        "1) Дела и мысли (детально)\n2) Чувства (кратко)\n3) Три победы\n4) StoryWorthy\n5) СДВГ (0–100)\n6) Action Points\n\n"
        "Команды: /newday — начать новый день, /summary — показать текущую сводку."
    )

@dp.message(Command("newday"))
async def newday(m: Message):
    SESSION[m.chat.id] = {
        "date": today_iso(),
        "structured": {},
        "awaiting": False,
        "questions": [],
        "skipped": set(),
        "awaiting_field": None
    }
    await m.answer("Окей, новый день. Запиши голосом или пришли текст.")

@dp.message(Command("summary"))
async def summary_cmd(m: Message):
    s = SESSION.get(m.chat.id)
    if not s or not s.get("structured"):
        return await m.answer("Пока нет данных за сегодня.")
    await m.answer(_render_summary(s.get("date", today_iso()), s["structured"])[:4000])

# ──────────────────────────────────────────────
# Core
# ──────────────────────────────────────────────
async def _ingest_text(m: Message, text: str):
    text = (text or "").strip()
    if not text:
        return await m.answer("Текста не вижу. Напиши пару фраз про день.")

    s = SESSION.get(m.chat.id)

    if s and s.get("awaiting") and s.get("structured"):
        prev = s["structured"]
        merged_raw = "\n".join([
            *prev.get("DayLog", []),
            f"Чувства: {prev.get('Feelings','')}",
            *prev.get("ThreeWins", []),
            f"История: {prev.get('StoryWorthy','')}",
            f"СДВГ: {prev.get('ADHDScore', 0)}",
            text
        ])
        data = structure_day(merged_raw)
    else:
        data = structure_day(text)

    qs = missing_questions(data)
    SESSION[m.chat.id] = {
        "date": today_iso(),
        "structured": data,
        "awaiting": bool(qs),
        "questions": qs,
        "skipped": set(),
        "awaiting_field": field_from_question(qs[0]) if qs else None
    }

    if qs:
        return await m.answer("Чуть уточню пустые места:\n- " + "\n- ".join(qs))

    await m.answer(_render_summary(today_iso(), data)[:4000])

# ──────────────────────────────────────────────
# Handlers
# ──────────────────────────────────────────────
@dp.message(F.text & ~F.via_bot)
async def handle_text(m: Message):
    s = SESSION.get(m.chat.id)
    if s and s.get("awaiting") and s.get("awaiting_field"):
        field = s["awaiting_field"]
        reply = (m.text or "").strip()

        if reply.lower() in NEG_WORDS:
            s["skipped"].add(field)
        else:
            if field == "StoryWorthy":
                s["structured"]["StoryWorthy"] = reply
            elif field == "Feelings":
                s["structured"]["Feelings"] = reply
            elif field == "ADHDScore":
                nums = [int(x) for x in "".join(ch if ch.isdigit() or ch==" " else " " for ch in reply).split() if x.isdigit()]
                s["structured"]["ADHDScore"] = nums[0] if nums else s["structured"].get("ADHDScore", 0)
            elif field == "ThreeWins":
                items = [p.strip(" .;,-") for p in reply.replace("\n", ",").split(",") if p.strip()]
                s["structured"]["ThreeWins"] = items[:3]
            elif field == "DayLog":
                items = [p.strip(" .;,-") for p in reply.replace("\n", ",").split(",") if p.strip()]
                s["structured"]["DayLog"] = (s["structured"].get("DayLog", []) + items)[:50]

        s["awaiting_field"] = None
        s["awaiting"] = False
        s["questions"] = []

        qs_all = missing_questions(s["structured"])
        qs = [q for q in qs_all if field_from_question(q) not in s["skipped"]]

        if qs:
            s["awaiting"] = True
            s["questions"] = qs
            s["awaiting_field"] = field_from_question(qs[0])
            return await m.answer("Ещё уточню:\n- " + "\n- ".join(qs))

        return await m.answer(_render_summary(s.get("date", today_iso()), s["structured"])[:4000])

    await _ingest_text(m, m.text)

@dp.message(F.voice | F.audio)
async def handle_audio(m: Message):
    tg_file = await bot.get_file(m.voice.file_id if m.voice else m.audio.file_id)
    ogg_path = tempfile.mktemp(suffix=".ogg")
    await bot.download_file(tg_file.file_path, destination=ogg_path)

    try:
        wav_path = ogg_to_wav(ogg_path)
        text = transcribe(wav_path)
    except Exception as e:
        return await m.answer(f"Не удалось распознать аудио: {e}")

    if not text:
        return await m.answer("Не распознал речь. Попробуй ещё раз.")

    await _ingest_text(m, text)

# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
async def main():
    print("Bot is running… Ctrl+C для остановки")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
