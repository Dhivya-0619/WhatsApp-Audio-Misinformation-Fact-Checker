from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from twilio.twiml.messaging_response import MessagingResponse

from . import claim_cache
from .claim_extractor import extract_claims
from .config import settings
from .counter_message import generate_counter_message
from .database import insert_claim
from .fact_checker import verify_claim
from .utils import format_whatsapp_reply, pick_language_fallback
from .virality_score import calculate_virality
from .whisper_transcriber import transcribe_audio


def _download_twilio_media(media_url: str, content_type: str | None) -> str:
    """
    Download media from Twilio's MediaUrl (requires basic auth).
    Returns local file path.
    """
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise RuntimeError("Missing TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN for media download")

    ext = "bin"
    if content_type:
        if "ogg" in content_type:
            ext = "ogg"
        elif "mpeg" in content_type or "mp3" in content_type:
            ext = "mp3"
        elif "wav" in content_type:
            ext = "wav"
        elif "mp4" in content_type or "m4a" in content_type:
            ext = "mp4"

    r = requests.get(
        media_url,
        auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        timeout=60,
    )
    r.raise_for_status()

    fd, tmp_path = tempfile.mkstemp(prefix="wa_voice_", suffix=f".{ext}")
    try:
        os.close(fd)
    except Exception:
        pass
    Path(tmp_path).write_bytes(r.content)
    return tmp_path


def process_voice_message(audio_file: str) -> Dict[str, Any]:
    """
    AI pipeline:
      1) transcribe
      2) extract claims
      3) cache check
      4) verify (if new)
      5) virality
      6) counter-message
      7) store
      8) return response object (for primary claim)
    """
    tr = transcribe_audio(audio_file)
    text = (tr.get("text") or "").strip()
    language = (tr.get("language") or "").strip() or None

    if not language:
        language = pick_language_fallback(text)

    claims_obj = extract_claims(text)
    claims = claims_obj.get("claims") or []
    if not claims:
        claims = [text[:400]] if text else []

    virality = calculate_virality(text)

    primary_result: Optional[Dict[str, Any]] = None

    for idx, claim in enumerate(claims[:5]):  # cap for hackathon safety
        cached = claim_cache.find_cached_claim(claim, threshold=0.85)
        if cached:
            verdict = (cached.get("verdict") or "uncertain").lower()
            confidence = int(cached.get("confidence") or 50)
            explanation = cached.get("explanation") or "Previously verified claim (cached)."
            sources = cached.get("sources") or []
            virality_score = int(cached.get("virality_score") or virality["score"])

            counter = generate_counter_message(claim, verdict, language)
            result = {
                "claim": claim,
                "language": cached.get("language") or language,
                "verdict": verdict,
                "confidence": confidence,
                "explanation": explanation,
                "sources": sources,
                "virality_score": virality_score,
                "virality_reasoning": cached.get("virality_reasoning") or virality["reasoning"],
                "counter_message": counter,
                "from_cache": True,
                "claim_id": cached.get("id"),
            }
        else:
            fc = verify_claim(claim)
            verdict = (fc.get("verdict") or "uncertain").lower()
            confidence = int(fc.get("confidence") or 50)
            explanation = fc.get("explanation") or ""
            sources = fc.get("sources") or []
            virality_score = int(virality["score"])

            counter = generate_counter_message(claim, verdict, language)
            claim_id = insert_claim(
                claim_text=claim,
                language=language,
                verdict=verdict,
                confidence=confidence,
                explanation=explanation,
                sources=sources,
                virality_score=virality_score,
            )
            result = {
                "claim": claim,
                "language": language,
                "verdict": verdict,
                "confidence": confidence,
                "explanation": explanation,
                "sources": sources,
                "virality_score": virality_score,
                "virality_reasoning": virality["reasoning"],
                "counter_message": counter,
                "from_cache": False,
                "claim_id": claim_id,
            }

        if idx == 0:
            primary_result = result

    if not primary_result:
        primary_result = {
            "claim": "",
            "language": language,
            "verdict": "uncertain",
            "confidence": 0,
            "explanation": (
                "Could not extract any claim from the audio. "
                "The audio may be in an unsupported format or the transcription failed. "
                "Try sending the claim as text."
            ),
            "sources": [],
            "virality_score": int(virality["score"]),
            "virality_reasoning": virality["reasoning"],
            "counter_message": generate_counter_message("", "uncertain", language),
            "from_cache": False,
            "claim_id": None,
        }

    return primary_result


def process_text_message(text: str) -> Dict[str, Any]:
    """
    AI pipeline for plain text messages (no audio):
      1) extract claims
      2) cache check
      3) verify (if new)
      4) virality
      5) counter-message
      6) store
      7) return response object (for primary claim)
    """
    text = (text or "").strip()
    language = pick_language_fallback(text)

    if not text:
        return {
            "claim": "",
            "language": language,
            "verdict": "uncertain",
            "confidence": 0,
            "explanation": "I did not receive any text to fact-check.",
            "sources": [],
            "virality_score": 1,
            "virality_reasoning": "no content",
            "counter_message": generate_counter_message("", "uncertain", language),
            "from_cache": False,
            "claim_id": None,
        }

    claims_obj = extract_claims(text)
    claims = claims_obj.get("claims") or []
    if not claims:
        claims = [text[:400]]

    virality = calculate_virality(text)

    primary_result: Optional[Dict[str, Any]] = None

    for idx, claim in enumerate(claims[:5]):
        cached = claim_cache.find_cached_claim(claim, threshold=0.85)
        if cached:
            verdict = (cached.get("verdict") or "uncertain").lower()
            confidence = int(cached.get("confidence") or 50)
            explanation = cached.get("explanation") or "Previously verified claim (cached)."
            sources = cached.get("sources") or []
            virality_score = int(cached.get("virality_score") or virality["score"])

            counter = generate_counter_message(claim, verdict, language)
            result = {
                "claim": claim,
                "language": cached.get("language") or language,
                "verdict": verdict,
                "confidence": confidence,
                "explanation": explanation,
                "sources": sources,
                "virality_score": virality_score,
                "virality_reasoning": cached.get("virality_reasoning") or virality["reasoning"],
                "counter_message": counter,
                "from_cache": True,
                "claim_id": cached.get("id"),
            }
        else:
            fc = verify_claim(claim)
            verdict = (fc.get("verdict") or "uncertain").lower()
            confidence = int(fc.get("confidence") or 50)
            explanation = fc.get("explanation") or ""
            sources = fc.get("sources") or []
            virality_score = int(virality["score"])

            counter = generate_counter_message(claim, verdict, language)
            claim_id = insert_claim(
                claim_text=claim,
                language=language,
                verdict=verdict,
                confidence=confidence,
                explanation=explanation,
                sources=sources,
                virality_score=virality_score,
            )
            result = {
                "claim": claim,
                "language": language,
                "verdict": verdict,
                "confidence": confidence,
                "explanation": explanation,
                "sources": sources,
                "virality_score": virality_score,
                "virality_reasoning": virality["reasoning"],
                "counter_message": counter,
                "from_cache": False,
                "claim_id": claim_id,
            }

        if idx == 0:
            primary_result = result

    if not primary_result:
        primary_result = {
            "claim": "",
            "language": language,
            "verdict": "uncertain",
            "confidence": 0,
            "explanation": "Could not extract any factual claim from this message.",
            "sources": [],
            "virality_score": int(virality["score"]),
            "virality_reasoning": virality["reasoning"],
            "counter_message": generate_counter_message("", "uncertain", language),
            "from_cache": False,
            "claim_id": None,
        }

    return primary_result


def handle_incoming_whatsapp(form: Dict[str, Any]) -> Tuple[str, int, str]:
    """
    Takes Twilio webhook form and returns (body, status_code, content_type).
    """
    num_media = int(form.get("NumMedia") or 0)
    body = (form.get("Body") or "").strip()

    resp = MessagingResponse()

    if num_media <= 0:
        # Text-only message: run text pipeline
        if body:
            try:
                result = process_text_message(body)
                resp.message(format_whatsapp_reply(result))
            except Exception:
                resp.message(
                    "Sorry—something went wrong while processing this message. "
                    "Please try again in a few minutes."
                )
        else:
            resp.message(
                "Please send a WhatsApp text containing a factual claim, or forward a voice note (audio)."
            )
        return str(resp), 200, "application/xml"

    media_url = form.get("MediaUrl0")
    media_type = form.get("MediaContentType0")  # e.g. audio/ogg

    if not media_url or (media_type and not media_type.startswith("audio/")):
        # Non-audio media: if there is text, try to fact-check the text instead.
        if body:
            try:
                result = process_text_message(body)
                resp.message(format_whatsapp_reply(result))
            except Exception:
                resp.message(
                    "I received media, but could not process it. "
                    "Please send a voice note or a text message containing a factual claim."
                )
        else:
            resp.message(
                "I received media, but it doesn't look like an audio message. "
                "Please send a voice note or a text message containing a factual claim."
            )
        return str(resp), 200, "application/xml"

    tmp_path = None
    try:
        tmp_path = _download_twilio_media(str(media_url), str(media_type) if media_type else None)
        result = process_voice_message(tmp_path)
        resp.message(format_whatsapp_reply(result))
        return str(resp), 200, "application/xml"
    except Exception:
        # Hide raw error details from end-users.
        resp.message(
            "Sorry—something went wrong while processing the audio message. "
            "Please try again later or send the core claim as text."
        )
        return str(resp), 200, "application/xml"
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

