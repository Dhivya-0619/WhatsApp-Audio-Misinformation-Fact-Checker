# WhatsApp Vernacular Audio Misininformation Fact-Checker

Build a WhatsApp bot that receives forwarded **voice messages**, transcribes them with **Whisper**, extracts factual claims with an **LLM**, verifies via **web search**, and replies with a **fact-check verdict** and **counter-message** in the same language.

## Project structure

```
project/
  backend/
    app/
      main.py
      config.py
      whatsapp_handler.py
      whisper_transcriber.py
      claim_extractor.py
      fact_checker.py
      virality_score.py
      counter_message.py
      claim_cache.py
      database.py
      models.py
      utils.py
    requirements.txt
  frontend/
    dashboard/
      index.html
      dashboard.js
    factchecker/
      index.html
      portal.js
  README.md
```

## Requirements

- Python **3.10**
- Twilio WhatsApp (Sandbox is fine)
- (Optional) OpenAI API key for Whisper + LLM
- (Optional) Tavily API key for web search verification

Note: **SQLite is built into Python** (`sqlite3`), no separate pip package needed.

## Environment variables

Create `backend/.env`:

```
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
WHISPER_MODEL=whisper-1

TAVILY_API_KEY=...

TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890

# Optional
DATABASE_URL=sqlite:///./claims.db
BACKEND_CORS_ORIGINS=*
```

If `OPENAI_API_KEY` or `TAVILY_API_KEY` are missing, the backend still runs (it will produce **UNCERTAIN** results with fallback behavior).

## Run backend (Windows PowerShell)

From the repo root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend starts at `http://localhost:8000`.

## Open the UIs (served by FastAPI)

- Dashboard: `http://localhost:8000/dashboard/`
- Fact-checker portal: `http://localhost:8000/portal/`

## Twilio WhatsApp setup

1. In Twilio Console, enable **WhatsApp Sandbox** (or a WhatsApp-enabled sender).
2. Expose your local server with ngrok (example):

```bash
ngrok http 8000
```

3. Set the **Incoming Messages** webhook URL to:
`https://<your-ngrok-subdomain>.ngrok-free.app/webhook/whatsapp`

Method: **POST**

4. Send a WhatsApp voice note to your Twilio number.

## API endpoints

- **POST** `/webhook/whatsapp`: Twilio WhatsApp webhook (receives voice note media, replies with TwiML)
- **GET** `/dashboard/stats`: dashboard analytics JSON
- **GET** `/claims`: list all claims stored in SQLite
- **POST** `/claims/update`: fact-checker updates to verdict, confidence, explanation, sources, disputed flag

## WhatsApp reply format

The bot replies like:

- Claim
- Verdict: TRUE / FALSE / UNCERTAIN
- Confidence %
- Explanation
- Virality Risk score (1–10)
- Correction message (same language)
- Top sources (up to 3)

