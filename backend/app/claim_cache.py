from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, Optional, Tuple

from .database import fetch_all_claims
from .utils import normalize_text


def _similarity(a: str, b: str) -> float:
    a_n = normalize_text(a)
    b_n = normalize_text(b)
    if not a_n or not b_n:
        return 0.0

    # Sequence similarity
    seq = SequenceMatcher(None, a_n, b_n).ratio()

    # Token Jaccard
    a_t = set(a_n.split())
    b_t = set(b_n.split())
    j = 0.0
    if a_t and b_t:
        j = len(a_t & b_t) / max(1, len(a_t | b_t))

    # Weighted blend
    return 0.65 * seq + 0.35 * j


def find_cached_claim(claim_text: str, threshold: float = 0.85) -> Optional[Dict[str, Any]]:
    """
    If a previously processed claim is sufficiently similar, return it (cache hit).
    """
    claim_text = (claim_text or "").strip()
    if not claim_text:
        return None

    candidates = fetch_all_claims()
    best: Tuple[float, Optional[Dict[str, Any]]] = (0.0, None)

    for c in candidates:
        sim = _similarity(claim_text, c.get("claim_text") or "")
        if sim > best[0]:
            best = (sim, c)

    if best[1] is not None and best[0] >= threshold:
        return best[1]
    return None

