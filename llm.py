# llm.py — обёртка над OpenAI для:
# 1) structure_day(text) -> str (ГОТОВЫЙ текст для Notion)
# 2) understand_task(text) -> str

from openai import OpenAI
from prompts import STRUCT_PROMPT, TASK_UNDERSTANDING_PROMPT

_client = OpenAI()  # OPENAI_API_KEY из окружения

def _chat(system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini") -> str:
    resp = _client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()

def structure_day(raw_text: str) -> str:
    """
    Возвращает ГОТОВЫЙ текст для Notion по правилам STRUCT_PROMPT.
    Внутри промпта используется триггер «История:/Story:» для StoryWorthy & Observations.
    """
    system = "Ты структурируешь дневник по заданному шаблону и возвращаешь только готовый текст."
    return _chat(system, STRUCT_PROMPT + (raw_text or ""))

def understand_task(raw_text: str) -> str:
    """
    Возвращает текстовую карточку задачи согласно TASK_UNDERSTANDING_PROMPT.
    """
    system = "Ты оформляешь описание задачи по шаблону, не выдумывая недостающих фактов."
    return _chat(system, TASK_UNDERSTANDING_PROMPT + (raw_text or ""))