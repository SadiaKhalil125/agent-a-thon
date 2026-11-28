# CompanyTwin AI — Agent-a-thon repo

**Organizational digital twin** demo for SSI Agent-A-Thon 2026: a seeded fictional company ("Northstar Systems") → a disruption → a visible multi-agent recovery flow → human approval → verified outcome. Product definition: [docs/PRD.md](./docs/PRD.md).

All company data is fabricated. No real client, customer or SSI data is used anywhere.

## How it works (one paragraph)

A deterministic solver (`twin/solver.py`) computes **every number**: what a disruption affects, who is free, what each plan costs, and whether a plan breaks anything. LangGraph agents (Impact, HR/Resource, Finance, Planner, Verifier) only **explain and recommend** through one LLM gateway. The Verifier's accept/reject decision comes from the solver, and nothing runs without a human approval. Details: [docs/architecture.md](./docs/architecture.md).

## Stack

Python 3.11+ · FastAPI · LangGraph · LangChain `ChatOpenAI` → LiteLLM-style gateway (server-side only) · vanilla HTML/JS UI (SSE) · Vercel Hobby · no database.

## Where things are

| Path | What |
|---|---|
| `twin/` | Company model, seed loader/validation, deterministic solver |
| `agents/` | LLM factory (`llm.py`), agent prompts (`roles.py`), node logic (`nodes.py`) |
| `orchestration/` | LangGraph state, budget, graph |
| `api/` | State, run (SSE) and execute/outcome routes |
| `data/seed/` | Seed company data (JSON) |
| `templates/`, `static/`, `branding.py` | Demo UI shell (owned by the frontend track) |
| `tests/` | pytest suite |
| `docs/` | Planning docs (source of truth) |

## Quick start

1. `python -m venv .venv` → activate → `pip install -r requirements-dev.txt`
2. Copy `.env.local.example` → `.env.local` and fill in `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`. The file is gitignored; **never commit or share the key**.
3. `uvicorn app:app` → http://localhost:8000 (restart after backend edits; there is no auto-reload on Windows)

Checks (run before claiming anything works):

```
ruff check . && ruff format --check . && mypy . && pytest -q
```

See **[DEPLOYMENT.md](./DEPLOYMENT.md)** for GitHub, Vercel and troubleshooting.

## Project status

This branch (`main`) holds the planning docs, tooling, CI and the module **skeleton** (stubs for `twin/`, `agents/`, `orchestration/` and `api/`).

The working backend (seed data, solver, LangGraph run with SSE, approval gate, hardening, and the local test console at `/dev`) lives on the branch **`feat/TASK-004-seed-model`** and is not merged into `main` yet. Its status and evidence are in `docs/memory.md` on that branch.

## Docs (read in this order)

1. [docs/PRD.md](./docs/PRD.md): what and why
2. [docs/architecture.md](./docs/architecture.md): how it works
3. [docs/design.md](./docs/design.md): demo UI
4. [docs/rules.md](./docs/rules.md): engineering and AI guardrails
5. [docs/phases.md](./docs/phases.md): build order and `TASK-*` tickets
6. [docs/memory.md](./docs/memory.md): current verified state
7. [docs/BUILD_PLAN.md](./docs/BUILD_PLAN.md): two-person parallel plan and file ownership

**AI / implementers:** [AGENTS.md](./AGENTS.md) · **Portal and deadlines:** [HACKATHON.md](./HACKATHON.md) · **UI spec:** [FRONTEND.md](./FRONTEND.md)
