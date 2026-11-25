# Agent-a-thon

Hackathon starter: **FastAPI** on Vercel, with LiteLLM for model access.

## Quick start

1. `python -m venv .venv` → activate → `pip install -r requirements.txt`
2. When organizers send your key: copy `.env.local.example` → `.env.local` and fill in the three values (you can build the UI and server before that — **Ask** will explain what's missing until then)
3. `uvicorn app:app --reload` → http://localhost:8000

See **[DEPLOYMENT.md](./DEPLOYMENT.md)** for GitHub, Vercel, submit checklist, and troubleshooting.

Official guide: https://ssi-ai-hackathon.vercel.app/guide