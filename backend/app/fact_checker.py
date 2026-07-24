from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import get_openai_key, settings
from .utils import chunk_sources_for_prompt, safe_json_loads


def _tavily_search(query: str, max_results: int = 6) -> List[Dict[str, Any]]:
    if not settings.TAVILY_API_KEY:
        return []

    from tavily import TavilyClient  # lazy import

    client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    resp = client.search(query=query, max_results=max_results, include_answer=False)
    # tavily-python returns { results: [ {title,url,content,...} ] }
    results = resp.get("results") or []
    if isinstance(results, list):
        return results
    return []


def verify_claim(claim: str) -> Dict[str, Any]:
    """
    Verify claim via web search (Tavily) + LLM reasoning.

    Returns:
      {
        verdict: "true/false/uncertain",
        confidence: 0-100,
        explanation: "...",
        sources: ["..."]
      }
    """
    claim = (claim or "").strip()
    if not claim:
        return {
            "verdict": "uncertain",
            "confidence": 0,
            "explanation": "No claim provided.",
            "sources": [],
        }

    sources_raw = _tavily_search(claim)
    urls: List[str] = []
    for r in sources_raw:
        u = (r.get("url") or "").strip()
        if u:
            urls.append(u)

    def _uncertain_fallback(explanation: str) -> Dict[str, Any]:
        return {
            "verdict": "uncertain",
            "confidence": 40 if urls else 20,
            "explanation": explanation,
            "sources": urls,
        }

    api_key = get_openai_key()
    if not api_key:
        # Runnable fallback: without LLM, we can't robustly determine truth.
        return _uncertain_fallback(
            "Automated verification requires an LLM API key. Sources were collected, but verdict is uncertain."
        )

    from openai import OpenAI  # lazy import

    client = OpenAI(api_key=api_key)

    prompt = (
        "Determine if the claim is TRUE, FALSE, or UNCERTAIN based ONLY on the sources.\n"
        "Return JSON exactly in this shape:\n"
        '{ \"verdict\": \"true|false|uncertain\", \"confidence\": 0-100, \"explanation\": \"short\", \"sources\": [\"url\", \"...\"] }\n\n'
        f"Claim:\n{claim}\n\n"
        "Sources:\n"
        f"{chunk_sources_for_prompt(sources_raw)}"
    )

    try:
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a careful fact-checking assistant."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        content = resp.choices[0].message.content or ""
        data = safe_json_loads(content) or {}
    except Exception:
        # e.g. quota exceeded or transient API failure
        return _uncertain_fallback(
            "Automated LLM-based verification is temporarily unavailable (for example due to quota limits). "
            "Sources were collected, but verdict is uncertain."
        )

    verdict = (data.get("verdict") or "uncertain").lower()
    if verdict not in ("true", "false", "uncertain"):
        verdict = "uncertain"
    confidence = data.get("confidence")
    try:
        confidence_int = int(confidence)
    except Exception:
        confidence_int = 50
    confidence_int = max(0, min(100, confidence_int))

    explanation = (data.get("explanation") or "").strip()
    if not explanation:
        explanation = "Could not confidently verify this claim from available sources."

    srcs = data.get("sources")
    if isinstance(srcs, list) and srcs:
        final_sources = [str(s).strip() for s in srcs if str(s).strip()][:6]
    else:
        final_sources = urls[:6]

    return {
        "verdict": verdict,
        "confidence": confidence_int,
        "explanation": explanation[:700],
        "sources": final_sources,
    }

