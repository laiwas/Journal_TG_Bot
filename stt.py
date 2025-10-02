# stt.py
# Лёгкая STT через OpenAI Whisper API.
# Принимаем путь к файлу (ogg/opus из Telegram подходит напрямую).

from openai import OpenAI

_client = OpenAI()  # ключ берётся из окружения: OPENAI_API_KEY

def ogg_to_wav(path: str) -> str:
    """
    Исторический интерфейс. Больше не нужен, возвращаем исходный путь.
    Оставлен ради совместимости, чтобы не ломать импорты.
    """
    return path

def transcribe(file_path: str, language: str = "ru") -> str:
    """
    Отправляет аудиофайл напрямую в OpenAI Whisper.
    Подходит для .ogg (opus), .mp3, .wav и т.д.
    """
    with open(file_path, "rb") as f:
        resp = _client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language=language,
        )
    return (resp.text or "").strip()