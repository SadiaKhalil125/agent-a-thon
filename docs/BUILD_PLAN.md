# Build Plan — CompanyTwin AI (2-day, built to win)

## Context
This is an SSI Agent-A-Thon entry; a strong placement matters to the owner. The five planning docs (PRD → architecture → design → rules → phases) are approved and `AGENTS.md` + `docs/memory.md` are initialized; no code exists yet. The LiteLLM key is available now, so we can run and deploy real agent calls from Day 1. Decision taken: **tight 6-agent set with a fully closed loop, polished and deployed**, over a broader-but-thinner roster.

The rubric rewards: end-to-end completeness **with visible multi-agent orchestration**, creativity, clean technical execution (key safe), a live easy-to-demo Vercel app, and business value. The winning shape is a **complete, visibly-orchestrated, repeatable** demo — not a half-built ambitious one.

## The key insight that drives sequencing
The agents are **not** the expensive part. Once the deterministic **solver**, the **step-loop plumbing**, the **base-agent scaffold**, and the **UI trail** exist, each additional agent role is just *a prompt + a slice of facts* — cheap to add. So we front-load the plumbing + solver, prove one real agent end-to-end on Vercel early, then multiply agents, then close the loop, then polish.

## Which agents to build, and in what order (the answer to "what first")
Build the **hero trio first** (they carry the demo), then the supporting specialists, then close the loop:

1. **Impact Investigator** — the twin's signature move: traces a disruption across departments (task → QA → milestone → customer → invoice). This is what makes it look like a *company twin*, not a chatbot.
2. **Planner** — produces ≥2 recovery options with real, compared trade-offs (dates, deadlines, cost). The business-value payoff.
3. **Verifier (skeptic)** — **rejects an infeasible plan and forces a revision.** This is THE differentiator that proves agents actually check each other (scores Completeness + Technical execution hardest). Non-negotiable for the win.
4. **Finance specialist** — the $8,000 invoice exposure vs. the $2,000 budget. Concrete money = business value.
5. **HR / Resource specialist** — the "backup is double-booked on Project B" insight. Shows real constraint reasoning.
6. **Execution agent** — applies the approved plan and verifies the outcome. Closes the loop.

The **Orchestrator** is the **LangGraph `StateGraph`** itself (nodes + edges + the conditional verifier→planner edge), not a separate model call. **Observer** and **Sales** are dropped from the core set and kept as cheap stretch nodes if Day 2 runs ahead. All six are **LangGraph nodes** — role prompt/parse units reaching the model only via `agents/llm.py` (`ChatOpenAI` → LiteLLM), per the revised ADR-002/003 (architecture v0.2). Specialists can run as **parallel nodes** (fan-out) to cut latency.

## Two-day schedule

### Day 1 — working core, deployed, real calls (end state: a live URL where you trigger the event and watch the Impact agent do real cross-department tracing)
- **Block 1 — Foundation (TASK-001, 003):** create module skeleton (`api/`, `orchestration/`, `agents/`, `twin/`, `data/seed/`, `tests/`), pin deps, configure Ruff + type check + pytest, and **deploy the skeleton to Vercel immediately** to de-risk platform config and confirm `vercel.json` needs.
- **Block 2 — Twin & Solver (TASK-004, 005, 006):** `data/seed/northstar.json` + loader/validation; twin model + dependency graph; **the deterministic solver** (impact chain, completion days, deadline impact, incremental cost, invoice eligibility, candidate plans) with unit tests. This is the backbone that makes every number correct and repeatable.
- **Block 3 — First real node end-to-end (TASK-008, 009, 010):** `ChatOpenAI`→LiteLLM factory (real key, one retry, honest failure) + injectable fake chat model; LangGraph **State + `StateGraph` skeleton** + node budget; then `POST /api/run/stream` running the **Impact** node with a real model call, **streamed** into a minimal trail, **on the live Vercel URL** (proves SSE + bundle on Vercel).
- **Day-1 milestone:** a deployed app that already looks like a multi-agent org twin doing real work.

### Day 2 — full orchestration, closed loop, polish, submit
- **Block 4 — Multiply agents + plans (TASK-011, 012):** add **HR** and **Finance** steps (reuse the base agent); **Planner** produces ≥2 compared plans from the solver's candidates.
- **Block 5 — The differentiator + closed loop (TASK-013, 007, 014):** **Verifier** reject→revise transition (capped at one revision); then approval gate → apply → outcome verification → reset. Now the loop is closed.
- **Block 6 — UI polish (TASK-015, 016, 017, 018):** company-state screen + dependency chain; agent trail with per-step states incl. **failed**; plan-comparison table with **fact tags** (Fact / Calculated / Estimate); approval bar + outcome panel + progress rail. This is where "easy to demo" is won.
- **Block 7 — Hardening + release (TASK-019, 020, 021, 023):** budget cap; honest failure / not-configured states; **key + real-data scan**; production deploy; **incognito smoke of Flow A**; ≤600-char submission summary.
- **Stretch only if ahead:** Observer + Sales as extra visible steps; a11y pass (TASK-022); a second constraint-conflict scenario (TASK-S3).

## Critical files to create (per architecture §5)
- `data/seed/northstar.json` — the fabricated company (hero of correctness).
- `twin/solver.py` + `twin/model.py` + `twin/seed.py` — deterministic core; **all numbers live here, no model calls**.
- `agents/nodes.py` + `agents/roles.py` + `agents/llm.py` — the 6 roles as LangGraph nodes over the shared `ChatOpenAI`→LiteLLM factory.
- `orchestration/state.py` + `graph.py` + `budget.py` — graph State, the `StateGraph` incl. the verifier→planner conditional edge, node/call budget.
- `api/state.py` + `api/run.py` (SSE `/api/run/stream`) + `api/execute.py` — endpoints; validate, stream, enforce budget, never call the model directly.
- `templates/index.html` (replace the single-prompt UI) + `static/js/run.js` (SSE client, + reuse `theme.js`) + extend `static/css/main.css`.
- `tests/test_solver.py`, `tests/test_graph.py`, `tests/test_security.py`.
- `app.py` (refactor to mount routers, keep `render_index`), `branding.py` (rebrand to CompanyTwin), `requirements.txt` (pin), optional `vercel.json`, `.github/workflows/ci.yml`.

## What makes it win (keep these front-and-center in the demo)
1. The twin **visibly connecting departments** (Impact step with evidence chips).
2. **Agents checking each other** — the Verifier rejecting a plan and the Planner revising it.
3. **Real numbers** from the solver, each tagged Fact/Calculated/Estimate → trustworthy, not hallucinated.
4. **Closed loop**: human approval → applied change → verified outcome.
5. **Live, repeatable, no presenter** — a judge re-runs it and can change an input.

## Risk management (deliberate choices)
- **Deploy Day 1**, not Day 2 — platform surprises surface early.
- **Numbers are deterministic** (solver), so no model-math errors and results are reproducible.
- **One model call per step + run budget** — public URL can't drain the capped key.
- **Fake chat model for CI** — graph nodes and the verifier conditional edge are tested without spending budget; real calls reserved for the live demo path.
- **Honest failure** — a failed model call shows a failed node, never fabricated text (protects the Technical-execution score and the owner's intent).
- **New LangGraph risks, front-loaded:** SSE streaming on Vercel (AR5) and langchain bundle size vs the function limit (AR6) are both proven on the Day-1 deploy (TASK-003/010); fallback for streaming is a buffered run returning the full trail.

## Verification (end-to-end)
- **Unit:** `pytest tests/test_solver.py` — impact chain, the three canonical plans, no double-booking, finance exposure, outcome check (AT-TWIN/IMP/PLAN/EXEC).
- **Integration:** `pytest tests/test_run_steps.py` with the test double — real-call occurrence, ordered steps, verifier rejection changes the plan, approval gate, budget cap, honest failure, deterministic re-run (AT-ORCH/EVENT/OPS/REL).
- **Security:** `pytest tests/test_security.py` + manual scan — no `sk-`/key in client/repo, no real data (AT-SEC).
- **Live smoke:** open the production `*.vercel.app` in an **incognito window** and complete Flow A unaided; confirm each agent step is real (server logs show one call/step) and the loop closes with a verified outcome (AT-UI-001, AT-PERF-001, AT-REL-002).

## First concrete step on approval
Create a `feat/TASK-001-scaffold` branch and execute **TASK-001** (module skeleton + tooling + pinned deps), running `ruff` + type check + `pytest` on the stub suite and reporting real output — then immediately **TASK-003** (skeleton deploy to Vercel) to de-risk the platform. (Owner decision first: commit the approved planning docs to Git before code, or branch straight into TASK-001.)
