import tempfile, subprocess
from faster_whisper import WhisperModel

_model = None

def _get_model():
    global _model
    if _model is None:
        _model = WhisperModel("small", device="cpu", compute_type="int8")
    return _model

def ogg_to_wav(ogg_path: str) -> str:
    wav_path = tempfile.mktemp(suffix=".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
    )
    return wav_path

def transcribe(path: str) -> str:
    model = _get_model()
    segments, _ = model.transcribe(path, vad_filter=True, language="ru")
    return "".join(seg.text for seg in segments).strip()
