# Execution Memory — CompanyTwin AI

> Evidence-based implementation state. Not a chat diary. Verify against Git, files and tests before trusting any line here.

## 1. Checkpoint metadata
- Project: CompanyTwin AI (organizational digital twin)
- Checkpoint: 2026-11-28
- Branch: `main` (no feature branch cut yet)
- Last verified commit: `3aa978d` — "updated-read me" (planning docs + AGENTS.md were committed by the owner in `19a377a`/`3aa978d`, outside this session)
- Active phase: **P0 Foundation**
- Active ticket: **TASK-001 — Verified complete.** Next: **TASK-003** (Vercel deploy — owner action) and **TASK-004** (seed data).
- Orchestration decision: **LangGraph** adopted (architecture **v0.2**, ADR-002/003 revised) on 2026-11-28; all five docs + AGENTS/README/HACKATHON synced; scaffold re-aligned; checks re-run green.

## 2. Validated completed work
- **TASK-001 — Scaffold, tooling & module skeleton — Verified complete (2026-11-28).**
  - Created module skeleton: `twin/` (`model.py`, `seed.py`, `solver.py`), `agents/` (`llm.py`, `nodes.py`, `roles.py`), `orchestration/` (`state.py`, `graph.py`, `budget.py`), `api/` (`state.py`, `run.py`, `execute.py`), `data/seed/.gitkeep`, `tests/test_scaffold.py` — all stubs with docstrings pointing to their owning ticket. (Original stubs `agents/litellm_client.py`, `agents/base.py`, `orchestration/context.py`, `orchestration/registry.py` were renamed/removed when LangGraph was adopted.)
  - Tooling: `pyproject.toml` (Ruff lint+format, mypy, pytest config), `requirements.txt` (pinned runtime + `langgraph==1.2.24`, `langchain-openai==1.8.5`), `requirements-dev.txt` (dev), `.github/workflows/ci.yml` (ruff + mypy + pytest on Python 3.11).
  - Resolved the rules.md "confirm at scaffold" items: **check command = `ruff check . && ruff format --check . && mypy . && pytest -q`**; type checker = **mypy**.
- Planning docs (PRD, architecture, design, rules, phases) + `AGENTS.md`: authored, approved, and **committed** (owner commits `19a377a`/`3aa978d`).

## 3. Current work
- TASK-001 closed. No ticket in progress right now (awaiting owner go-ahead on commit + the next build block).
- Files inspected/modified this session: created all scaffold files above; **reformatted existing `app.py` and `branding.py`** with `ruff format` to meet the new standard (formatting-only; no logic change). The single-prompt `/api/chat` + `chat.js` still exist and will be replaced in TASK-010/016.
- Uncommitted: everything new (scaffold, docs, `AGENTS.md`, CI) is untracked; `app.py`/`branding.py` modified (format only). `.venv/` is gitignored.

## 4. Last verification (real evidence, 2026-11-28)
- Environment: local `.venv`, **Python 3.11.9**, deps from `requirements-dev.txt`.
- `ruff check .` → **All checks passed!**
- `ruff format --check .` → **30 files already formatted**
- `mypy .` → **Success: no issues found in 19 source files**
- `pytest -q` → **1 passed** (`tests/test_scaffold.py::test_packages_import`)
- LLM: a development provider is configured **only** in `.env.local` (gitignored) — base_url/model + a **placeholder key**; the owner pastes the real key into `.env.local` (`LLM_API_KEY`) before any real call. No provider name is in tracked files. The existing `/api/chat` then works as an immediate smoke test; agent nodes begin at TASK-010. Not yet verified against the live endpoint (no key entered here).

## 5. Outstanding blockers / notes
- **Deviation from docs (non-blocking):** local toolchain is **Python 3.11.9**, not 3.12; targeted `>=3.11` in `pyproject.toml`/CI. Vercel runtime can still be 3.12. Update the docs' "3.12" references if we standardize on 3.11.
- **`openai` pinned at 3.60.0**; model is now reached via LangChain `ChatOpenAI` (`langchain-openai==1.8.5`) at TASK-008 — confirm the `base_url`/`api_key`/`model` call works against the LiteLLM gateway.
- **AR4 (TASK-003):** Vercel `/api` serverless-function convention may conflict with our internal `api/` routes package. Verify on first deploy with the FastAPI preset; `vercel.json` intentionally NOT added yet.
- **AR5 (TASK-010):** SSE streaming on Vercel Python functions — must be proven on the first streamed graph run; fallback is a buffered run returning the full trail.
- **AR6 (TASK-003):** langchain/langgraph bundle vs Vercel's function size limit — measure on first deploy (local site-packages ~176 MB incl. dev tools; runtime subset smaller). Trim if over.
- Deadline (R7): confirm Nov 29 vs Nov 30 2:00 PM PKT.

## 6. Approved changes / decisions (by reference)
- PRD v0.1, architecture v0.1 (ADR-001…004), design v0.1, rules v0.1, phases v0.1 — Approved 2026-11-27.
- Build plan approved 2026-11-28: tight 6-agent set + closed loop; deploy early; key available.
- **LangGraph adopted 2026-11-28** (owner decision): orchestration = LangGraph `StateGraph`, streamed SSE run, verifier→planner conditional edge, parallel specialist nodes; execution a separate post-approval request. Architecture v0.2, rules v0.2, phases v0.2.
- **Provider config made neutral 2026-11-28** (owner decision): the app targets any OpenAI-compatible gateway; the chosen provider lives **only** in `.env.local` (gitignored) — the LiteLLM gateway for submission. New `config.py` resolves `LLM_BASE_URL/API_KEY/MODEL` (legacy `LITELLM_*` fallback); `app.py` health field renamed to `llm_configured`; `.env.local.example` uses generic placeholders. **No provider name appears in any tracked file** (owner requirement). Docs (PRD §10, architecture, rules, AGENTS, DEPLOYMENT, HACKATHON) synced.

## 7. Next actions (smallest safe steps)
1. **Owner decision:** commit the TASK-001 scaffold to Git (planning docs are already committed), or continue building first.
2. **TASK-003 (owner):** connect GitHub + Vercel, deploy the skeleton with the FastAPI preset, set env vars (`LLM_*`; the LiteLLM gateway for submission), and confirm `/api/*` routing (AR4). Report the live URL.
3. **TASK-004 (next build block):** author `data/seed/northstar.json` (fabricated Northstar scenario from PRD §10) + loader/validation in `twin/seed.py` + `twin/model.py`; unit test AT-TWIN-001-01.
4. Then **TASK-006** solver (the backbone), **TASK-008** `ChatOpenAI`→LiteLLM factory, **TASK-009** LangGraph State + `StateGraph` skeleton.

## 8. Handoff instructions
Read `AGENTS.md`, the approved docs in order, then this file. Activate the local `.venv` (`.venv/Scripts/python`). Verify Git status and run the check command before claiming progress. Work the active ticket only; report real command output; mark anything not run as `Not run`. Update this file at the next verified checkpoint.
