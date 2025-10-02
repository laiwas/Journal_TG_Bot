import tempfile, subprocess
from openai import OpenAI

client = OpenAI()  # API-ключ уже должен быть в окружении: OPENAI_API_KEY

def ogg_to_wav(ogg_path: str) -> str:
    wav_path = tempfile.mktemp(suffix=".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
    )
    return wav_path

def transcribe(path: str) -> str:
    wav_path = ogg_to_wav(path)

    with open(wav_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="ru"
        )

    return transcript.text.strip()
