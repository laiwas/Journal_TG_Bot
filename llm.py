import os, json
from openai import OpenAI
from dotenv import load_dotenv
from prompts import STRUCT_PROMPT, MISSING_PROMPT

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("Не найден OPENAI_API_KEY в .env")

client = OpenAI(api_key=api_key)

def _chat(prompt: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.choices[0].message.content.strip()

def _clean(s: str) -> str:
    s = s.strip().strip("`")
    if s.lower().startswith("json"):
        s = s[4:].strip()
    return s

def structure_day(raw_text: str) -> dict:
    out = _chat(STRUCT_PROMPT + raw_text)
    data = json.loads(_clean(out))

    # гарантируем наличие всех ключей
    default = {
        "DayLog": [],
        "Feelings": "",
        "ThreeWins": [],
        "StoryWorthy": "",
        "ADHDScore": 0,
        "ActionPoints": {
            "BookRead": False,
            "NotesDone": False,
            "RPG": False,
            "Finance": False
        }
    }
    # мягкое слияние (если ActionPoints отсутствует — подставим пустые)
    default.update({k: data.get(k, default[k]) for k in default.keys()})
    # внутри ActionPoints — тоже мягкое слияние
    ap = default["ActionPoints"]
    ap_src = data.get("ActionPoints") or {}
    ap.update({
        "BookRead":  bool(ap_src.get("BookRead",  ap["BookRead"])),
        "NotesDone": bool(ap_src.get("NotesDone", ap["NotesDone"])),
        "RPG":       bool(ap_src.get("RPG",       ap["RPG"])),
        "Finance":   bool(ap_src.get("Finance",   ap["Finance"]))
    })
    default["ActionPoints"] = ap
    return default

def missing_questions(structured: dict) -> list[str]:
    # спрашиваем только про основные секции, ActionPoints оставляем как есть
    qs = []
    if not structured.get("DayLog"): qs.append("Какие дела и мысли были сегодня?")
    if not structured.get("Feelings"): qs.append("Как ты себя суммарно чувствовал?")
    if not structured.get("ThreeWins"): qs.append("Какие 3 победы/достижения за день?")
    if not structured.get("StoryWorthy"): qs.append("Была ли история или момент, который запомнился?")
    if not structured.get("ADHDScore"): qs.append("Оцени СДВГ от 0 до 100")
    return qs[:4]
