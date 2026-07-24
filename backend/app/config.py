import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend/ and project root (regardless of cwd)
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _BACKEND_DIR.parent
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv(_BACKEND_DIR / ".env")


def get_openai_key() -> str | None:
    """Read OpenAI key at runtime from env (avoids stale import-time cache)."""
    return os.environ.get("OPENAI_API_KEY") or None


@dataclass(frozen=True)
class Settings:
    # OpenAI / LLM (read at runtime via get_openai_key() to avoid stale cache)
    OPENAI_API_KEY: str | None = None  # Use get_openai_key() instead
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "whisper-1")

    # Tavily search
    TAVILY_API_KEY: str | None = os.getenv("TAVILY_API_KEY")

    # Twilio / WhatsApp
    TWILIO_ACCOUNT_SID: str | None = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str | None = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_WHATSAPP_NUMBER: str | None = os.getenv("TWILIO_WHATSAPP_NUMBER")  # 'whatsapp:+123...'

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./claims.db")

    # CORS / backend (comma-separated or '*')
    BACKEND_CORS_ORIGINS: str = os.getenv("BACKEND_CORS_ORIGINS", "*")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

