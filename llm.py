# llm.py — тонкая обёртка над OpenAI для двух функций:
# 1) structure_day(text) -> dict
# 2) understand_task(text) -> str

import os
import json
from dotenv import load_dotenv
from openai import OpenAI

from prompts import STRUCT_PROMPT, TASK_UNDERSTANDING_PROMPT

# ──────────────────────────────────────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────────────────────────────────────
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("Не найден OPENAI_API_KEY в .env")

client = OpenAI(api_key=api_key)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _chat(prompt: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.choices[0].message.content.strip()

def _clean_json(s: str) -> str:
    s = s.strip().strip("`")
    if s.lower().startswith("json"):
        s = s[4:].strip()
    return s

# ──────────────────────────────────────────────────────────────────────────────
# День: структура
# ──────────────────────────────────────────────────────────────────────────────
def structure_day(raw_text: str) -> dict:
    """
    Возвращает dict строго под ожидаемую схему, даже если модель вернула что-то неполное.
    """
    out = _chat(STRUCT_PROMPT + (raw_text or ""))
    try:
        data = json.loads(_clean_json(out))
    except Exception:
        # страховка: если вдруг вернулся не-JSON
        data = {}

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

    # Мягкое слияние (не перетираем структуру ActionPoints)
    for k, v in default.items():
        if k == "ActionPoints":
            ap_src = (data.get("ActionPoints") or {})
            default["ActionPoints"].update({
                "BookRead":  bool(ap_src.get("BookRead",  default["ActionPoints"]["BookRead"])),
                "NotesDone": bool(ap_src.get("NotesDone", default["ActionPoints"]["NotesDone"])),
                "RPG":       bool(ap_src.get("RPG",       default["ActionPoints"]["RPG"])),
                "Finance":   bool(ap_src.get("Finance",   default["ActionPoints"]["Finance"])),
            })
        else:
            if k in data and data[k] is not None:
                default[k] = data[k]
    return default

# ──────────────────────────────────────────────────────────────────────────────
# Понимание задачи
# ──────────────────────────────────────────────────────────────────────────────
def understand_task(raw_text: str) -> str:
    """
    Возвращает готовый текст по структуре из TASK_UNDERSTANDING_PROMPT.
    Никакого JSON — формат ровно как в промпте (разделы построчно).
    """
    prompt = TASK_UNDERSTANDING_PROMPT.strip() + "\n\nТекст:\n" + (raw_text or "").strip()
    out = _chat(prompt)
    return out.strip()