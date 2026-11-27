# Execution Memory — CompanyTwin AI

> Evidence-based implementation state. Not a chat diary. Verify against Git, files and tests before trusting any line here.

## 1. Checkpoint metadata
- Project: CompanyTwin AI (organizational digital twin)
- Checkpoint: 2026-11-27 (planning complete; implementation not started)
- Branch: `main`
- Last verified commit: `e7488c9` — "Test change"
- Active phase: **P0 Foundation**
- Active ticket: **TASK-001 — Scaffold, tooling & module skeleton** (selected, `Not started`)

## 2. Validated completed work
- **Planning only.** All five planning docs authored and approved in conversation (PRD, architecture, design, rules, phases) + `AGENTS.md`.
  - Evidence: files exist under `docs/` and repo root; **currently untracked in Git** (`git status` shows `?? docs/`, `?? AGENTS.md`). Approvals are conversational, not yet committed.
- **No implementation tickets complete.** TASK-001…023: `Not started`.

## 3. Current work
- Ticket: TASK-001 — `Not started`.
- Files actually inspected this session: existing repo files (`app.py`, `branding.py`, `templates/index.html`, `static/js/{chat.js,theme.js}`, `requirements.txt`, `.env.local.example`, docs). No source modules created yet.
- Uncommitted changes: the new `docs/*.md` and `AGENTS.md` (untracked); no code changes.

## 4. Last verification
- Commands run: `git branch/status/log` only.
- Tests: **Not run** (no test suite exists yet).
- Lint/type/build: **Not run** (tooling configured in TASK-001).
- Environment: LiteLLM **not configured** (no key yet; `/api/health` would report `litellm_configured: false`). Not required until TASK-010.

## 5. Outstanding blockers
- None blocking P0/P1. The deterministic solver, twin, and UI shell (P0–P1, P5 foundations) build without the LiteLLM key.
- Awaiting (non-blocking): LiteLLM key/model id (needed at TASK-010); confirm submission deadline (R7).

## 6. Approved changes / decisions (by reference)
- PRD v0.1, architecture v0.1 (ADR-001 solver owns numbers; ADR-002 client-driven step loop; ADR-003 FastAPI; ADR-004 no DB), design v0.1, rules v0.1, phases v0.1 — all Approved in conversation on 2026-11-27.
- Owner name removed from all docs (generic "Participant").

## 7. Next actions (smallest safe steps)
1. **Begin TASK-001** (on a branch `feat/TASK-001-scaffold`): create the module skeleton (`api/`, `orchestration/`, `agents/`, `twin/`, `data/seed/`, `tests/`), pin `requirements.txt` + dev deps, configure Ruff + type checker + pytest, and finalize the check commands (resolving the "confirm at scaffold" items in rules §2/§8).
2. Run `ruff` + typecheck + `pytest` on the stub suite; record real output.
3. Optionally commit the approved planning docs first (owner decision) so the plan is in version control before code.

## 8. Handoff instructions
Read `AGENTS.md`, then the approved docs in order, then this file. Verify Git branch/status/history and actual files before writing code. Work only the active ticket (TASK-001) within its scope. Report real command evidence; mark anything not run as `Not run`. Update this file at the next meaningful verified checkpoint.
