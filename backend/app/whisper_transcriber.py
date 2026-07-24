from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .config import get_openai_key, settings
from .utils import convert_audio_to_mp3, pick_language_fallback


_FALLBACK_MODEL = None


def _get_fallback_model():
    """Lazy-load faster-whisper model (cached)."""
    global _FALLBACK_MODEL
    if _FALLBACK_MODEL is None:
        from faster_whisper import WhisperModel
        _FALLBACK_MODEL = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _FALLBACK_MODEL


def _transcribe_with_faster_whisper(audio_path: str) -> Dict[str, Optional[str]]:
    """Local transcription fallback when OpenAI Whisper fails. Uses PyAV (no ffmpeg install)."""
    try:
        model = _get_fallback_model()
        segments, info = model.transcribe(audio_path)
        text = " ".join(s.text for s in segments if s.text).strip()
        language = getattr(info, "language", None) or (pick_language_fallback(text) if text else "en")
        return {"text": text, "language": language}
    except Exception:
        return {"text": "", "language": None}


def transcribe_audio(file_path: str) -> Dict[str, Optional[str]]:
    """
    Transcribe an audio file. Uses OpenAI Whisper first, faster-whisper (local) as fallback.
    Converts OGG/Opus to MP3 for WhatsApp voice note compatibility.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    path_to_use = file_path
    converted_path: str | None = None
    ext = path.suffix.lower()

    # Always convert OGG/Opus/WebM to MP3 (WhatsApp voice notes)
    if ext in (".ogg", ".opus", ".oga", ".webm"):
        converted_path = convert_audio_to_mp3(file_path)
        if converted_path and converted_path != file_path:
            path_to_use = converted_path

    result: Dict[str, Optional[str]] = {"text": "", "language": None}

    # 1. Try OpenAI Whisper
    api_key = get_openai_key()
    if api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            with Path(path_to_use).open("rb") as f:
                resp = client.audio.transcriptions.create(
                    model=settings.WHISPER_MODEL,
                    file=f,
                    response_format="verbose_json",
                )
            text = getattr(resp, "text", None) or ""
            language = getattr(resp, "language", None)
            if text:
                if not language:
                    language = pick_language_fallback(text)
                result = {"text": text, "language": language}
        except Exception:
            pass

    # 2. If empty, use faster-whisper (local, no API, handles OGG via PyAV)
    if not (result.get("text") or "").strip():
        result = _transcribe_with_faster_whisper(path_to_use)
        if not result.get("language") and result.get("text"):
            result["language"] = pick_language_fallback(result["text"])

    # 3. Last resort: try original file with faster-whisper
    if not (result.get("text") or "").strip() and path_to_use != file_path:
        result = _transcribe_with_faster_whisper(file_path)
        if not result.get("language") and result.get("text"):
            result["language"] = pick_language_fallback(result["text"])

    if converted_path and Path(converted_path).exists() and converted_path != file_path:
        try:
            Path(converted_path).unlink(missing_ok=True)
        except Exception:
            pass

    return result

