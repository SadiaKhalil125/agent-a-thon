# CompanyTwin AI — Agent-a-thon repo

**Organizational digital twin** demo for SSI Agent-A-Thon 2026: seeded company → disruption → visible multi-agent recovery flow → approve → verify ([docs/PRD.md](./docs/PRD.md)).

**AI / implementers:** [AGENTS.md](./AGENTS.md) · **Portal / deadlines:** [HACKATHON.md](./HACKATHON.md) · **Tasks:** [docs/phases.md](./docs/phases.md) · **Status:** [docs/memory.md](./docs/memory.md) (active: **TASK-001**).

Stack: Python 3.12 · FastAPI · LiteLLM (server-side) · Vercel. Repo code is still the **chat starter**; build follows phases from TASK-001.

## Quick start

1. `python -m venv .venv` → activate → `pip install -r requirements.txt`
2. When organizers send your key: copy `.env.local.example` → `.env.local` and fill in the three values
3. `uvicorn app:app --reload` → http://localhost:8000

See **[DEPLOYMENT.md](./DEPLOYMENT.md)** for GitHub, Vercel, and troubleshooting.

**UI (starter shell):** [FRONTEND.md](./FRONTEND.md) — demo UI spec in [docs/design.md](./docs/design.md) (extends tokens over time).