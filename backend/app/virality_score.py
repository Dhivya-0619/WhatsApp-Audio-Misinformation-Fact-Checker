from __future__ import annotations

import re
from typing import Dict


URGENT = [
    "urgent",
    "immediately",
    "right now",
    "asap",
    "act now",
    "warning",
    "alert",
    "dont ignore",
    "do not ignore",
]
FORWARD = [
    "forward",
    "share",
    "send to",
    "spread",
    "everyone",
    "all contacts",
    "groups",
    "broadcast",
]
CONSPIRACY = [
    "they don't want you to know",
    "hidden truth",
    "cover up",
    "coverup",
    "secret",
    "banned",
    "censored",
]
EMOTION = [
    "shocking",
    "terrifying",
    "heartbreaking",
    "outrage",
    "anger",
    "fear",
    "panic",
]


def calculate_virality(text: str) -> Dict[str, object]:
    """
    Score 1-10 based on simple heuristics:
      urgency + forward calls + emotional manipulation + conspiratorial language
    """
    t = (text or "").lower()
    t = re.sub(r"\s+", " ", t)

    points = 0
    reasons = []

    def hit(phrases, weight, label):
        nonlocal points
        count = sum(1 for p in phrases if p in t)
        if count:
            points += weight * count
            reasons.append(f"{label} x{count}")

    hit(URGENT, 2, "urgency")
    hit(FORWARD, 3, "call-to-forward")
    hit(CONSPIRACY, 2, "conspiracy framing")
    hit(EMOTION, 1, "emotional manipulation")

    # exclamation / caps
    ex = t.count("!")
    if ex >= 3:
        points += 2
        reasons.append("many exclamations")

    # Clamp and map to 1..10
    score = 1 + min(9, points // 2)
    if score > 10:
        score = 10

    reasoning = " + ".join(reasons) if reasons else "low virality signals detected"
    return {"score": int(score), "reasoning": reasoning}

