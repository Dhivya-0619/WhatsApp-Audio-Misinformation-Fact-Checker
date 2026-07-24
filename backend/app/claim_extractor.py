from __future__ import annotations

from typing import Dict, List

from .config import get_openai_key, settings
from .utils import safe_json_loads


SYSTEM_PROMPT = (
    "You extract factual claims from user messages. "
    "Return ONLY valid JSON."
)


def extract_claims(text: str) -> Dict[str, List[str]]:
    """
    Extract factual claims from the given text.

    Returns:
      { "claims": ["..."] }
    """
    text = (text or "").strip()
    if not text:
        return {"claims": []}

    api_key = get_openai_key()
    if not api_key:
        # Simple heuristic fallback: treat the whole message as one claim if it looks like a claim
        return {"claims": [text[:400]]}

    from openai import OpenAI  # lazy import

    client = OpenAI(api_key=api_key)
    user_prompt = (
        "Extract factual claims from the following message.\n"
        "Return JSON in the shape:\n"
        '{ "claims": ["..."] }\n\n'
        f"Message:\n{text}"
    )

    try:
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = resp.choices[0].message.content or ""
        data = safe_json_loads(content) or {}
    except Exception:
        # On quota / network errors, fall back to treating the whole message as one claim.
        return {"claims": [text[:400]]}

    claims = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(claims, list):
        return {"claims": [text[:400]]}

    cleaned: List[str] = []
    for c in claims:
        if isinstance(c, str):
            s = c.strip()
            if s:
                cleaned.append(s[:400])
    # de-dup preserve order
    seen = set()
    uniq: List[str] = []
    for c in cleaned:
        k = c.lower()
        if k not in seen:
            uniq.append(c)
            seen.add(k)
    return {"claims": uniq}

