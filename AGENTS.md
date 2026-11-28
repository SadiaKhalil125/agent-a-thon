# AI Agent Instructions — CompanyTwin AI

Entry point for any AI coding agent (Claude Code / Cursor) working in this repository.
This file points to the approved plan; it does not duplicate it.

## Read first (approved planning docs — source of truth, in order)
1. `docs/PRD.md` — what & why (FR/NFR/AC/AT).
2. `docs/architecture.md` — how it works (FastAPI/Python; deterministic solver; client-driven step loop; 4 ADRs).
3. `docs/design.md` — the demo UI (single-page guided flow; fact-type tagging).
4. `docs/rules.md` — enforceable engineering & AI guardrails. **Obey these.**
5. `docs/phases.md` — build order and `TASK-*` tickets with traceability.
6. `docs/memory.md` — current *verified* implementation state. Read before acting; trust Git/tests over it.

## How to work
- Work **one approved `TASK-*` at a time**, within its scope. The active ticket is in `docs/memory.md`.
- Use **Accept-Edits** mode; review each change. No unattended full-auto edits.
- Before claiming progress, **run the checks and report real evidence** (commands + output). Never invent test/CI/deploy results. Report `Not run` when a check can't run.
- Verify Git status and files before editing; reconcile any discrepancy with `docs/memory.md`.

## Hard rules (from rules.md — non-negotiable)
- The LLM key is **server-side only**, resolved in `config.py` from `LLM_BASE_URL/API_KEY/MODEL` (legacy `LITELLM_*` accepted); `.env.local` gitignored. The provider is chosen in the environment only (LiteLLM gateway for submission) — a change of values, not code. Never commit, log, or expose the key to the browser.
- **Fabricated/public data only** — no real client/customer/SSI data anywhere, including tests.
- Orchestration is a **LangGraph `StateGraph`** (`orchestration/graph.py`); the verifier→planner revision is a conditional edge (capped once). Agents are graph nodes; the model is reached only via `agents/llm.py` (`ChatOpenAI` → LiteLLM).
- `twin/solver.py` computes **all numbers** and makes **no** model calls; `agents/*` (nodes) never compute numbers; `api/*` never calls the model directly.
- **One model call per graph node**; respect the run budget. On model failure, produce a `failed` node event with **no fabricated content**.
- Changes to contracts, security boundaries, dependencies, or the Vercel production project require **owner approval**.

## Boundaries
- Allowed in a ticket: read docs/files; implement bounded code+tests; run `ruff`/types/`pytest`; report evidence.
- Approval required: new/upgraded dependency; API/solver/seed-schema or security-boundary change; anything touching prod/env vars.
- Forbidden: secrets in code/docs/logs; fabricated results; bypassing validation/approval-gate/budget; silent scope expansion; real data.

## Commands (confirm/finalize in TASK-001)
`ruff check . && ruff format --check . && <typecheck> && pytest -q`

## Stack
Python 3.11+ · FastAPI · **LangGraph** orchestration · LangChain `ChatOpenAI` → LiteLLM gateway · vanilla HTML/JS UI (SSE) · Vercel Hobby · no database.
