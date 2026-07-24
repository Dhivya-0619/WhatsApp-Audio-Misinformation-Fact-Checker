import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from .config import settings


def _get_db_path() -> Path:
    if settings.DATABASE_URL.startswith("sqlite:///"):
        return Path(settings.DATABASE_URL.replace("sqlite:///", ""))
    # Fallback: treat as plain file path
    return Path(settings.DATABASE_URL)


DB_PATH = _get_db_path()


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_text TEXT NOT NULL,
                language TEXT,
                verdict TEXT,
                confidence INTEGER,
                explanation TEXT,
                sources TEXT,
                virality_score INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                disputed INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()


def insert_claim(
    claim_text: str,
    language: Optional[str],
    verdict: Optional[str],
    confidence: Optional[int],
    explanation: Optional[str],
    sources: Optional[List[str]],
    virality_score: Optional[int],
    disputed: bool = False,
) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO claims (
                claim_text, language, verdict, confidence,
                explanation, sources, virality_score, disputed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim_text,
                language,
                verdict,
                confidence,
                explanation,
                json.dumps(sources or []),
                virality_score,
                1 if disputed else 0,
            ),
        )
        return int(cur.lastrowid)


def fetch_all_claims() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, claim_text, language, verdict, confidence,
                   explanation, sources, virality_score, timestamp, disputed
            FROM claims
            ORDER BY timestamp DESC
            """
        )
        rows = cur.fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "id": row["id"],
                "claim_text": row["claim_text"],
                "language": row["language"],
                "verdict": row["verdict"],
                "confidence": row["confidence"],
                "explanation": row["explanation"],
                "sources": json.loads(row["sources"] or "[]"),
                "virality_score": row["virality_score"],
                "timestamp": row["timestamp"],
                "disputed": bool(row["disputed"]),
            }
        )
    return results


def update_claim_verdict(
    claim_id: int,
    verdict: Optional[str],
    confidence: Optional[int],
    explanation: Optional[str],
    sources: Optional[List[str]],
    disputed: Optional[bool] = None,
) -> None:
    fields: List[str] = []
    params: List[Any] = []

    if verdict is not None:
        fields.append("verdict = ?")
        params.append(verdict)
    if confidence is not None:
        fields.append("confidence = ?")
        params.append(confidence)
    if explanation is not None:
        fields.append("explanation = ?")
        params.append(explanation)
    if sources is not None:
        fields.append("sources = ?")
        params.append(json.dumps(sources))
    if disputed is not None:
        fields.append("disputed = ?")
        params.append(1 if disputed else 0)

    if not fields:
        return

    params.append(claim_id)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE claims SET {', '.join(fields)} WHERE id = ?", params  # nosec B608
        )


def get_dashboard_stats() -> Dict[str, Any]:
    with get_connection() as conn:
        cur = conn.cursor()

        # Total messages / claims
        cur.execute("SELECT COUNT(*) AS total FROM claims")
        total = int(cur.fetchone()["total"])

        # Verdict counts
        cur.execute(
            "SELECT verdict, COUNT(*) AS count FROM claims GROUP BY verdict"
        )
        verdict_counts: Dict[str, int] = {}
        for row in cur.fetchall():
            verdict = row["verdict"] or "unknown"
            verdict_counts[verdict] = int(row["count"])

        # Language distribution
        cur.execute(
            "SELECT language, COUNT(*) AS count FROM claims GROUP BY language"
        )
        language_distribution: Dict[str, int] = {}
        for row in cur.fetchall():
            lang = row["language"] or "unknown"
            language_distribution[lang] = int(row["count"])

        # Top viral claims (highest virality scores)
        cur.execute(
            """
            SELECT claim_text, virality_score, COUNT(*) AS occurrences
            FROM claims
            WHERE virality_score IS NOT NULL
            GROUP BY claim_text, virality_score
            ORDER BY virality_score DESC, occurrences DESC
            LIMIT 10
            """
        )
        top_viral_claims: List[Dict[str, Any]] = []
        for row in cur.fetchall():
            top_viral_claims.append(
                {
                    "claim_text": row["claim_text"],
                    "virality_score": row["virality_score"],
                    "occurrences": row["occurrences"],
                }
            )

    # Simple false vs true structure for charts
    false_vs_true = {
        "true": verdict_counts.get("true", 0),
        "false": verdict_counts.get("false", 0),
        "uncertain": verdict_counts.get("uncertain", 0),
    }

    # Very simple "trending categories" heuristic based on keywords
    categories = {
        "health": ["covid", "vaccine", "cancer", "cure", "doctor", "hospital"],
        "politics": ["election", "government", "minister", "president", "vote"],
        "finance": ["bank", "loan", "tax", "investment", "scheme"],
        "security": ["terrorist", "attack", "riot", "crime", "kidnap"],
    }
    trending_categories: Dict[str, int] = {k: 0 for k in categories}

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT claim_text FROM claims")
        for (claim_text,) in cur.fetchall():  # type: ignore[misc]
            text_lower = (claim_text or "").lower()
            for cat, keywords in categories.items():
                if any(word in text_lower for word in keywords):
                    trending_categories[cat] += 1

    return {
        "total_messages": total,
        "verdict_counts": verdict_counts,
        "language_distribution": language_distribution,
        "top_viral_claims": top_viral_claims,
        "false_vs_true": false_vs_true,
        "trending_categories": trending_categories,
    }

