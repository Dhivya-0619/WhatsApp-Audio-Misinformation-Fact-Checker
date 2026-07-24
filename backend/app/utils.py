import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# Human-readable language names for responses
LANGUAGE_NAMES: Dict[str, str] = {
    "en": "English",
    "ta": "Tamil",
    "hi": "Hindi",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "ur": "Urdu",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "pt": "Portuguese",
}


def safe_json_loads(text: str) -> Any:
    """
    Best-effort JSON parsing for LLM outputs that may wrap JSON in text.
    """
    text = text.strip()
    # Try direct
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try extract first JSON object/array
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            return None
    return None


def normalize_text(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s]", "", s)
    return s


def chunk_sources_for_prompt(sources: List[Dict[str, Any]], limit: int = 6) -> str:
    lines: List[str] = []
    for item in sources[:limit]:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        content = (item.get("content") or item.get("snippet") or "").strip()
        if content:
            content = re.sub(r"\s+", " ", content)
        lines.append(f"- {title}\n  {url}\n  {content}".strip())
    return "\n".join(lines).strip()


def get_language_display_name(code: str | None) -> str:
    """Return human-readable language name for response display."""
    if not code:
        return "Unknown"
    return LANGUAGE_NAMES.get((code or "").lower(), (code or "").upper())


def _get_ffmpeg_path() -> str | None:
    """Get ffmpeg executable path (bundled via imageio-ffmpeg or system)."""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        return None


def convert_audio_to_mp3(input_path: str) -> str | None:
    """
    Convert OGG/Opus/other audio to MP3 for Whisper compatibility.
    Uses imageio-ffmpeg's bundled ffmpeg first, then pydub as fallback.
    Returns path to MP3 file, or None if conversion fails.
    """
    path = Path(input_path)
    if not path.exists():
        return None

    ext = path.suffix.lower()
    if ext in (".mp3", ".mpeg", ".mpga", ".m4a", ".wav"):
        return input_path  # Already supported by Whisper

    # 1. Try ffmpeg via subprocess (bundled imageio-ffmpeg - no user install needed)
    ffmpeg_path = _get_ffmpeg_path()
    if ffmpeg_path:
        import subprocess

        out_path = path.with_suffix(".mp3")
        try:
            subprocess.run(
                [
                    ffmpeg_path,
                    "-i",
                    str(path),
                    "-vn",
                    "-acodec",
                    "libmp3lame",
                    "-y",
                    str(out_path),
                ],
                capture_output=True,
                timeout=60,
                check=True,
            )
            if out_path.exists():
                return str(out_path)
        except Exception:
            pass

    # 2. Fallback: pydub (uses bundled ffmpeg if available)
    try:
        from pydub import AudioSegment

        if ffmpeg_path:
            AudioSegment.converter = str(ffmpeg_path)
            AudioSegment.ffmpeg = str(ffmpeg_path)

        fmt = ext.lstrip(".") or None
        if fmt == "opus":
            fmt = "ogg"
        audio = AudioSegment.from_file(str(path), format=fmt)
        out_path = path.with_suffix(".mp3")
        audio.export(str(out_path), format="mp3", bitrate="128k")
        return str(out_path)
    except Exception:
        return None


def pick_language_fallback(text: str) -> str:
    """
    Very rough fallback language guess when Whisper/LLM doesn't provide language.
    """
    # Basic script heuristics
    for ch in text:
        code = ord(ch)
        if 0x0B80 <= code <= 0x0BFF:
            return "ta"
        if 0x0900 <= code <= 0x097F:
            return "hi"
        if 0x0C00 <= code <= 0x0C7F:
            return "te"
    return "en"


def format_whatsapp_reply(result: Dict[str, Any]) -> str:
    claim = result.get("claim") or ""
    verdict = (result.get("verdict") or "uncertain").upper()
    confidence = result.get("confidence") if result.get("confidence") is not None else 0
    explanation = result.get("explanation") or ""
    virality_score = result.get("virality_score") if result.get("virality_score") is not None else 1
    counter_message = result.get("counter_message") or ""
    sources = result.get("sources") or []
    language = result.get("language")
    lang_display = get_language_display_name(language)

    sources_block = ""
    if sources:
        short = sources[:3]
        sources_block = "\n\nSources:\n" + "\n".join([f"- {u}" for u in short])

    return (
        "⚠ Fact Check Result\n\n"
        f"Detected Language: {lang_display}\n\n"
        f"Claim: {claim}\n\n"
        f"Verdict: {verdict}\n\n"
        f"Confidence: {confidence}%\n\n"
        "Explanation:\n"
        f"{explanation}\n\n"
        f"Virality Risk: {virality_score}/10\n\n"
        "Correction Message:\n"
        f"{counter_message}"
        f"{sources_block}"
    )

