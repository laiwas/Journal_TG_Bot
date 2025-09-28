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

def _clean_json(s: str) -> str:
    s = s.strip().strip("`")
    if s.lower().startswith("json"):
        s = s[4:].strip()
    return s

# ── День: структура ───────────────────────────────────────────────────────────

def structure_day(raw_text: str) -> dict:
    out = _chat(STRUCT_PROMPT + raw_text)
    data = json.loads(_clean_json(out))
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
    # мягкое слияние
    default.update({k: data.get(k, default[k]) for k in default.keys()})
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

# ── Понимание задачи ──────────────────────────────────────────────────────────

def understand_task(raw_text: str) -> str:
    """
    Возвращает готовый текст по структуре из TASK_PROMPT/TAKS_PROMPT.
    Никакого JSON — формат ровно как в промпте (разделы построчно).
    """
    prompt = TASK_PROMPT.strip() + "\n\nТекст:\n" + raw_text.strip()
    out = _chat(prompt)
    return out.strip()