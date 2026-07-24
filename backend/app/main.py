from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import Body, FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import fetch_all_claims, get_dashboard_stats, init_db, update_claim_verdict
from .models import DashboardStats, UpdateClaimRequest
from .whatsapp_handler import handle_incoming_whatsapp


app = FastAPI(title="WhatsApp Vernacular Audio Misinformation Fact-Checker")


def _cors_origins() -> List[str]:
    raw = (settings.BACKEND_CORS_ORIGINS or "*").strip()
    if raw == "*":
        return ["*"]
    return [x.strip() for x in raw.split(",") if x.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()

    # Mount frontend as static (integrated)
    # repo_root = .../vibecode
    repo_root = Path(__file__).resolve().parents[2]
    frontend = repo_root / "frontend"
    if (frontend / "dashboard").exists():
        app.mount("/dashboard", StaticFiles(directory=str(frontend / "dashboard"), html=True), name="dashboard")
    if (frontend / "factchecker").exists():
        app.mount("/portal", StaticFiles(directory=str(frontend / "factchecker"), html=True), name="portal")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


@app.get("/")
def home() -> RedirectResponse:
    return RedirectResponse(url="/dashboard/")


@app.post("/webhook/whatsapp")
async def webhook_whatsapp(request: Request) -> Response:
    form = await request.form()
    payload = dict(form)
    body, status, content_type = handle_incoming_whatsapp(payload)
    return Response(content=body, status_code=status, media_type=content_type)


@app.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats() -> Dict[str, Any]:
    return get_dashboard_stats()


@app.get("/claims")
def claims() -> List[Dict[str, Any]]:
    return fetch_all_claims()


@app.post("/claims/update")
def claims_update(payload: UpdateClaimRequest = Body(...)) -> Dict[str, Any]:
    update_claim_verdict(
        claim_id=payload.id,
        verdict=payload.verdict,
        confidence=payload.confidence,
        explanation=payload.explanation,
        sources=payload.sources,
        disputed=payload.disputed,
    )
    return {"ok": True}

