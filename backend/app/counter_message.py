from __future__ import annotations

from typing import Dict

from .config import get_openai_key, settings


TEMPLATES: Dict[str, str] = {
    "en": "Health experts and reliable sources do not support this claim. Please verify before forwarding.",
    "hi": "विश्वसनीय स्रोत इस दावे की पुष्टि नहीं करते। कृपया आगे भेजने से पहले सत्यापन करें।",
    "ta": "நம்பகமான ஆதாரங்கள் இந்தக் கூற்றை உறுதிப்படுத்தவில்லை. பகிர்வதற்கு முன் சரிபார்க்கவும்.",
    "te": "నమ్మకమైన వనరులు ఈ দাবును నిర్ధారించలేదు. దయచేసి ముందుకు పంపే ముందు ధృవీకరించండి.",
}


def generate_counter_message(claim: str, verdict: str, language: str | None) -> str:
    """
    If verdict is false, generate a short correction in the same language (2-3 sentences max).
    """
    lang = (language or "en").lower()
    verdict_norm = (verdict or "").lower()

    if verdict_norm != "false":
        # For true/uncertain, encourage verification.
        base = TEMPLATES.get(lang, TEMPLATES["en"])
        return base

    api_key = get_openai_key()
    if not api_key:
        return TEMPLATES.get(lang, TEMPLATES["en"])

    from openai import OpenAI  # lazy import

    client = OpenAI(api_key=api_key)
    prompt = (
        "Generate a short counter-message correcting misinformation.\n"
        "Constraints:\n"
        "- Same language as requested.\n"
        "- 2-3 sentences max.\n"
        "- Calm, non-judgmental.\n\n"
        f"Language: {lang}\n"
        f"Claim: {claim}\n"
        "Return only the message text."
    )

    try:
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You write short public-facing corrections."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )
        return (resp.choices[0].message.content or TEMPLATES.get(lang, TEMPLATES["en"])).strip()
    except Exception:
        # On quota / network errors, fall back to a simple template in the right language.
        return TEMPLATES.get(lang, TEMPLATES["en"])

