# Phases & Tickets — CompanyTwin AI
Project: CompanyTwin AI (organizational digital twin)
Complexity: Standard
Status: Draft
Version: 0.3
Owner: Participant
Last updated: 2026-11-28
Based on: docs/PRD.md v0.2, docs/architecture.md v0.3, docs/design.md v0.1, docs/rules.md v0.3, docs/BUILD_PLAN.md v2

> **v0.3 (2026-11-28):** adds the **simulated-connectors** tickets **TASK-024…028** (PRD v0.2 Domain INT, P2), a **track assignment** (Person A engine / Person B experience, §4a), `docs/contracts.md`, and the INT rows of the traceability matrix. TASK-011 retitled to the implemented specialist set (HR/Resource + Finance; Observer/Sales stretch) per BUILD_PLAN v2. All v0.2 IDs and links are unchanged.

> v0.2: orchestration is **LangGraph** (architecture ADR-002/003 revised). Affected tickets (008, 009, 010, 012, 013, 014) and the risk table updated below; IDs and traceability unchanged. TASK-001 already added `langgraph`/`langchain-openai` to `requirements.txt`.

> Build order and tickets. Every in-scope FR/NFR maps to ≥1 `TASK-*` and the acceptance tests it must satisfy (traceability §8). "Affected files" are **indicative** (most do not exist yet); the existing files are those in the current repo. No memory file is created here — that is Stage 6.

---

## 1. Delivery objective & scope

**MVP boundary (release target):** a public Vercel URL where an evaluator completes **Flow A** unaided — company state → disruption → visible multi-agent investigation → ≥2 compared recovery plans → a verifier rejection-and-revision → approval → applied state change → verified outcome — with the key server-side and fabricated data only.

**In scope:** all **P1** FR/NFR from the PRD. **Deferred (P2/P3):** custom event params (FR-EVENT-003), relationship graph view (FR-TWIN-003), constraint-conflict second scenario (FR-PLAN-004 full variant), synthetic permission demo (FR-SEC-003), passcode/throttle hardening beyond bounded calls (optional within NFR-OPS). These have stretch tickets but do **not** gate release.

**Guiding sequencing principle (hackathon "working core first"):** get **one agent path end-to-end on Vercel early** (TASK-010) to de-risk the 5-min/stateless/real-call pattern before building the full roster.

---

## 2. Phase / milestone map

| Phase | Goal | Exit criterion |
|---|---|---|
| **P0 Foundation** | Repo scaffold, tooling, CI, rebrand, LiteLLM wrapper, **early skeleton deploy**. | App deploys to Vercel; `ruff`+`pytest` run in CI; health endpoint green. |
| **P1 Twin & Solver** | Deterministic core: seed, model, solver (numbers + candidate plans + outcome). | Solver unit tests green for the primary scenario's known chain. |
| **P2 Core agent slice** | The LangGraph graph runs one node (Impact) end-to-end, **streamed** to the UI, with a **real** model call, budgeted. | Impact node runs on Vercel via `/api/run/stream`, visible, within budget; node failure handled honestly. |
| **P3 Full orchestration** | Remaining agents, handoffs, planner (≥2 plans), verifier reject→revise. | Full trail runs; a rejection produces a revised plan. |
| **P4 Execution loop** | Approval gate, execute, outcome verification, reset. | No change without approval; outcome reports match/mismatch; reset restores seed. |
| **P5 UI build-out** | Full demo flow, agent trail, plan comparison, fact tags, states. | Flow A completable unaided; all design states present. |
| *(v0.3, cross-cutting)* **Simulated connectors** | Tickets 024–026 (engine, P3/P4) and 027a–c (UI, P5), after TASK-010; P2, cut-line protected. | Hub, trail chips, event inbox, Action Center and audit log work in mock and live mode; all labeled Simulated. |
| **P6 Hardening & release** | Budget cap, honest failure/not-configured, security scan, a11y/responsive, prod deploy + submission. | All P1 ATs pass/recorded; incognito smoke clean; submission package ready. |

---

## 3. Dependency plan

- **Critical prerequisites:** LiteLLM key (external, organizer) — blocks real-call tests in P2+ but **not** P0/P1 (solver + UI shell build without it; use the test double). Vercel project + GitHub repo (P0).
- **Risky integration tested early:** TASK-003 (skeleton deploy — also proves the **langchain bundle size** AR6 and routing AR4) and TASK-010 (first streamed graph run on Vercel — proves **SSE streaming** AR5 and the 5-min budget) front-load the platform risks.
- **Sequence rationale:** deterministic solver (P1) before agents (P2/P3) so agent output has trustworthy numbers to narrate (ADR-001); execution (P4) after plans exist; UI (P5) after the API contract is stable; hardening/release (P6) last.
- **External blockers:** model id/gateway TBD (R1); deadline (R7).

---

## 4. Ticket register

| ID | Title | Phase | Pri | Status | Depends on | Links (FR / NFR / AT) |
|---|---|---|---|---|---|---|
| TASK-001 | Scaffold, tooling & module skeleton | P0 | P1 | Planned | — | rules §2/§8; NFR-MAINT-001 |
| TASK-002 | Rebrand to CompanyTwin + health | P0 | P1 | Planned | 001 | FR-SEC-001; AT-SEC-001-01 |
| TASK-003 | Early Vercel skeleton deploy + CI | P0 | P1 | Planned | 001,002 | NFR-REL-002; AT-REL-002-01 |
| TASK-004 | Seed data `northstar.json` + loader/validation | P1 | P1 | Done (local) | 001 | FR-TWIN-001; AT-TWIN-001-01 |
| TASK-005 | Twin model + dependency graph | P1 | P1 | Done (local) | 004 | FR-TWIN-001/003 |
| TASK-006 | Solver: schedule / completion / cost / eligibility + candidate plans | P1 | P1 | Done (local) | 005 | FR-IMP-001/003, FR-PLAN-001/002/003; AT-IMP-001/003, AT-PLAN-001/002 |
| TASK-007 | Solver: apply plan + outcome verification | P1 | P1 | Done (local) | 006 | FR-EXEC-002/003; AT-EXEC-002/003 |
| TASK-008 | LangChain `ChatOpenAI`→LiteLLM factory (`agents/llm.py`) + fake chat model | P0/P2 | P1 | Done (local) | 001 | FR-ORCH-002/005; AT-ORCH-002/005 |
| TASK-009 | LangGraph State + `StateGraph` skeleton + node budget | P2 | P1 | Done (local) | 005,008 | FR-ORCH-001, NFR-OPS-001, NFR-REL-001; AT-OPS-001, AT-REL-001 |
| TASK-010 | **Core slice:** `/api/run/stream` runs the graph, Impact node streamed end-to-end on Vercel | P2 | P1 | Local done; Vercel not run | 006,009 | FR-EVENT-001, FR-ORCH-002/003, FR-IMP-001; AT-EVENT-001, AT-ORCH-002/003, AT-IMP-001, AT-PERF-001 |
| TASK-011 | Specialist nodes: HR/Resource + Finance (parallel fan-out); Observer/Sales only as stretch | P3 | P1 | Done (local) | 010 | FR-IMP-002/003/004; AT-IMP-002/003 |
| TASK-012 | Planner step → ≥2 plans from solver candidates | P3 | P1 | Done (local) | 010,006 | FR-PLAN-001/002/003; AT-PLAN-001/002/003 |
| TASK-013 | Verifier step + reject→revise transition | P3 | P1 | Done (local) | 012 | FR-VER-001/002/003, FR-ORCH-004; AT-ORCH-004, AT-VER-003 |
| TASK-014 | Approval gate + execute + outcome endpoints | P4 | P1 | Done (local) | 007,013 | FR-EXEC-001/002/003/004; AT-EXEC-001/002/003/004 |
| TASK-015 | UI: company state §1 + dependency chain | P5 | P1 | Planned | 004,010 | FR-TWIN-002, FR-UI-001; AT-TWIN-002 |
| TASK-016 | UI: agent trail + step states (incl. failed) | P5 | P1 | Planned | 010,013 | FR-ORCH-003/005, FR-UI-001; AT-ORCH-003/005 |
| TASK-017 | UI: plan comparison + verdict + fact tags | P5 | P1 | Planned | 012,013 | FR-UI-002, FR-PLAN-002, FR-VER-003, NFR-USE-001; AT-USE-001 |
| TASK-018 | UI: approval bar + outcome + reset + progress rail | P5 | P1 | Planned | 014 | FR-EXEC-001, FR-UI-001/003; AT-UI-001 |
| TASK-019 | Hardening: budget cap enforcement (+ optional passcode) | P6 | P1 | Done (local) | 009 | NFR-OPS-001; AT-OPS-001 |
| TASK-020 | Honest failure + not-configured + deterministic re-run | P6 | P1 | Done (local) | 010,008 | FR-ORCH-005, NFR-REL-001, FR-EVENT-002; AT-ORCH-005, AT-EVENT-002, AT-REL-001 |
| TASK-021 | Security: key/data scan + input-validation negatives | P6 | P1 | Done (local) | 014 | FR-SEC-001/002, NFR-SEC-002; AT-SEC-001/002 |
| TASK-022 | Accessibility + responsive pass | P6 | P1 | Planned | 015-018 | NFR-USE-002; AT-USE-002 |
| TASK-023 | Release: prod deploy, incognito smoke, submission package | P6 | P1 | Planned | all P1 | NFR-REL-002; release gate §7 |
| TASK-024 | Connectors core: `integrations/` Connector base + manifests + registry; tier-1 read adapters (hris, tracker, erp, crm, calendar); `/mock/*`; `GET /api/integrations` (+`/sample`) | P3 | P2 | Done (local) | 004,005,010 | FR-INT-001, FR-INT-006; AT-INT-001, AT-INT-006, AT-INT-sec-01 |
| TASK-025 | Read-through + event inbox: nodes cite connector records and emit `integration_call`; presets from different systems as demo-HMAC webhooks; `evidenceUsed[].source`; `audit[]` | P3 | P2 | Planned | 024,011,012 | FR-INT-002, FR-INT-003, FR-INT-005; AT-INT-002, AT-INT-003, AT-INT-005 |
| TASK-026 | Action Center (engine): ActionBuilders per system; `plannedActions[]` dry run; `actions[]` with idempotency keys in `/api/execute`; `reread[]` in `/api/outcome` | P4 | P2 | Planned | 024,007,014 | FR-INT-004, FR-INT-005; AT-INT-004, AT-INT-005, AT-INT-sec-01 |
| TASK-027a | UI: Connected Systems hub (tiles by tier, manifest chips, payload drawer) + event inbox preset cards | P5 | P2 | Planned | 002,015 (mock until 024/025) | FR-INT-001, FR-INT-003, FR-INT-006; AT-INT-006 |
| TASK-027b | UI: integration-call chips in the agent trail + source links on evidence chips | P5 | P2 | Planned | 016 (mock until 025) | FR-INT-002, FR-INT-006; AT-INT-002, AT-INT-006 |
| TASK-027c | UI: Action Center (dry-run grid, artifact cards, idempotency chips), audit log drawer, re-read confirmation | P5 | P2 | Planned | 018 (mock until 026) | FR-INT-004, FR-INT-005, FR-INT-006; AT-INT-004, AT-INT-005, AT-INT-006 |
| TASK-028 | (Stretch) Tier-3 connectors: vendor management, spreadsheet read, meet transcript; `X-Simulate-Outage` honest degradation | — | P3 | Planned | 024,025 | FR-INT-001, FR-INT-006; AT-INT-006 |
| TASK-S1 | (Stretch) Custom event params | — | P3 | Planned | 010 | FR-EVENT-003 |
| TASK-S2 | (Stretch) Relationship graph view | — | P3 | Planned | 015 | FR-TWIN-003 |
| TASK-S3 | (Stretch) Constraint-conflict 2nd scenario | — | P2 | Planned | 012 | FR-PLAN-004; AT-PLAN-004 |
| TASK-S4 | (Stretch) Synthetic permission demo | — | P3 | Planned | 015 | FR-SEC-003 |

### 4a. Track assignment (two people in parallel; see `docs/BUILD_PLAN.md` v2 §4, §7, §8)

| Track | Owner | Tickets (in order) |
|---|---|---|
| **A — Engine** | Person A | 004, 005, 006, 007, 008, 009, 010, **024**, 011, 012, 013, **025**, 014, **026**, 019, 020, 021, 028 (stretch); A also lands the C0 docs change-control commit and cleans up `/api/chat` |
| **B — Experience** | Person B | 002, 015, 016, 017, 018, **027a, 027b, 027c**, 022; B also builds `static/js/api-client.js` + `static/mock/` (live/mock switch) and flips to live at the end |
| **Together** | both | 001/003 (done), `docs/contracts.md` at C0, 023 release |

Sync points C0–C5 and cut lines for the integration tickets are in BUILD_PLAN §6 and §9. TASK-024…026 start only after TASK-010 (Day-1 milestone).

---

## 5. Ticket details (representative; all others follow the §ticket template with their register links)

### TASK-001: Scaffold, tooling & module skeleton
Status: Planned · Priority: P1 · Phase: P0 · Links: rules §2/§8, NFR-MAINT-001 · Depends on: None
Objective: Create the module skeleton (`api/`, `orchestration/`, `agents/`, `twin/`, `data/seed/`, `tests/`) and resolve the deferred tool configs.
In scope: folder/package skeleton with stubs; pin `requirements.txt` + dev deps; configure Ruff, type checker, pytest; define the exact check commands (resolves rules §2/§8 "confirm at scaffold").
Out of scope: any feature logic; model calls.
Affected files: `requirements.txt` (existing), `ruff.toml`/`pyproject`, `tests/`, package stubs, `app.py` (existing, split into routers).
Implementation notes: keep dependency direction `api→orchestration→{agents,twin}`; `twin.solver` import-pure.
Verification: `ruff check . && ruff format --check . && <typecheck> && pytest -q` run green on an empty/stub suite; commands recorded.
Definition of done: tooling runs locally and is ready for CI (TASK-003); no feature code.

### TASK-006: Solver — schedule, completion, cost, eligibility + candidate plans
Status: Planned · Priority: P1 · Phase: P1 · Links: FR-IMP-001/003, FR-PLAN-001/002/003; AT-IMP-001/003, AT-PLAN-001/002 · Depends on: TASK-005
Objective: Deterministically compute, for the primary scenario, the impact chain and the candidate recovery plans with completion days, deadline impact, incremental cost and invoice eligibility.
In scope: pure functions over the twin model; the known chain (integration→QA→milestone→invoice); the three canonical options (wait / reassign backup / contractor) with correct numbers and the backup's Project-B conflict respected.
Out of scope: model calls; UI; applying a plan (TASK-007).
Affected files: `twin/solver.py`, `tests/test_solver.py`.
Implementation notes: no I/O; seeded; numbers are the authority (ADR-001). Represent "day" as working-day integers per the seed.
Verification: unit tests assert the full impact chain (AT-IMP-001-01), finance exposure vs budget (AT-IMP-003-01), ≥2 distinct plans (AT-PLAN-001-01), comparable trade-off fields (AT-PLAN-002-01), no double-booking (AT-IMP-002-01).
Definition of done: all listed unit tests green with output recorded; coverage of the primary chain complete.

### TASK-008: LangChain ChatOpenAI → LiteLLM factory
Status: Planned · Priority: P1 · Phase: P0/P2 · Links: FR-ORCH-002/005; AT-ORCH-002/005 · Depends on: TASK-001
Objective: A server-side factory that builds a `ChatOpenAI(base_url, api_key, model)` from env pointed at the LiteLLM gateway, with timeout, **one** bounded retry and structured error; plus an injectable **fake chat model** for tests.
In scope: `agents/llm.py` factory + error taxonomy mapping (rules §6); a LangChain fake/stub chat model that asserts invocation and can simulate failure.
Out of scope: node prompts/roles (TASK-010/011); the graph + budget (TASK-009).
Affected files: `agents/llm.py` (renamed from the TASK-001 stub `litellm_client.py`), `tests/` helpers.
Implementation notes: never log key/payload; retry at most once; raise `UpstreamModelError` on failure (no fabricated content). The factory is the only place the model is constructed.
Verification: a graph/node test proves a model call happens (AT-ORCH-002-01) and a simulated failure surfaces as a failed node with no content (AT-ORCH-005-01) — using the fake model, no paid call.
Definition of done: factory + fake model tested green; key never logged (asserted).

### TASK-010: Core graph slice end-to-end (the de-risk ticket)
Status: Planned · Priority: P1 · Phase: P2 · Links: FR-EVENT-001, FR-ORCH-002/003, FR-IMP-001; AT-EVENT-001, AT-ORCH-002/003, AT-IMP-001, AT-PERF-001 · Depends on: TASK-006, TASK-009
Objective: A one-node LangGraph graph running end-to-end **on Vercel**: `POST /api/run/stream {presetId}` → the Impact node (real model call) → **streamed** node event → visible result, within budget and the 5-min ceiling.
In scope: the `/api/run/stream` SSE endpoint; the graph with the Impact node; minimal trail rendering from the stream; a real ChatOpenAI→LiteLLM call behind the node; solver supplies the facts the node narrates.
Out of scope: other nodes, plans, verifier, execution, full UI.
Affected files: `api/run.py`, `orchestration/graph.py`+`state.py`+`budget.py`, `agents/nodes.py`+`roles.py` (Impact only)+`llm.py`, `templates/index.html`+`static/js/run.js` (SSE client).
Implementation notes: exactly one model call per node; recompute facts server-side; the run is self-contained (no server-memory dependence between requests). **This ticket proves AR5 (SSE on Vercel) and AR6 (bundle size).**
Verification: AT-EVENT-001-01 (preset starts the graph), AT-ORCH-002-01 (real call), AT-ORCH-003-01 (ordered streamed node), AT-IMP-001-01 (full chain), AT-PERF-001-01 (run < 5 min); deployed and exercised on the Vercel URL.
Definition of done: the slice runs on the production URL with evidence; honest node-failure path present (ties to TASK-020).

### TASK-013: Verifier + reject→revise
Status: Planned · Priority: P1 · Phase: P3 · Links: FR-VER-001/002/003, FR-ORCH-004; AT-ORCH-004, AT-VER-003 · Depends on: TASK-012
Objective: A Verifier step that can reject an infeasible/unsupported plan with a reason, driving a single revised Planner output that addresses the objection.
In scope: verifier node + the one-time Planner→Verifier→Planner **conditional edge** in `orchestration/graph.py`; a seeded rejectable candidate for deterministic testing.
Out of scope: unbounded revise loops (cap = 1).
Affected files: `agents/nodes.py`+`roles.py`, `orchestration/graph.py`, tests.
Verification: AT-ORCH-004-01 (rejection changes the plan, references objection), AT-VER-003-01 (verdict+reason visible).
Definition of done: rejection→revision demonstrated deterministically; verdict surfaced to UI contract.

### TASK-014: Approval gate + execute + outcome
Status: Planned · Priority: P1 · Phase: P4 · Links: FR-EXEC-001/002/003/004; AT-EXEC-001/002/003/004 · Depends on: TASK-007, TASK-013
Objective: a **separate request after the streamed graph run** — `/api/execute {presetId, approvedPlanId}` applies the plan via the solver; `/api/outcome` re-checks vs the selected plan; `/api/reset` restores seed.
In scope: the approval-gated execution (self-contained request, no model call), outcome verification, reset; no external calls during execution.
Out of scope: UI (TASK-018).
Affected files: `api/execute.py`, `twin/solver.py` (apply/outcome from TASK-007), tests.
Verification: AT-EXEC-001 (no change without approval), AT-EXEC-002 (applied), AT-EXEC-003 (match/mismatch), AT-EXEC-004 (reset + no external call).
Definition of done: all four EXEC ATs green; approval gate proven server-side.

### TASK-024: Connectors core (simulated)
Status: Planned · Priority: P2 · Phase: P3 · Links: FR-INT-001, FR-INT-006; AT-INT-001, AT-INT-006, AT-INT-sec-01 · Depends on: TASK-004, 005, 010
Objective: A `Connector` base, per-system manifest (category, tier, auth mode, scopes, rate limit, capabilities), registry and tier-1 read adapters (hris, tracker, erp, crm, calendar) as pure views over the seed, exposed at `/mock/*` and via `GET /api/integrations` (+`/{id}/sample`).
In scope: `integrations/{base,manifest,registry,hris,tracker,erp,crm,calendar}.py`, `api/integrations.py`, `source{system, externalId}` on seed entities, OpenAPI tag "Simulated connectors", `tests/test_integrations.py`.
Out of scope: action sinks (TASK-026); node wiring (TASK-025); tier-3 (TASK-028); any real vendor, network or credential.
Affected files: `integrations/`, `api/integrations.py`, `app.py` (mount), `data/seed/northstar.json` (source fields — additive), `tests/test_integrations.py`.
Implementation notes: in-process; no HTTP client import in `integrations/`; every manifest `mode:"simulated"`; confirm `/mock/*` deploys on Vercel (AR7).
Verification: AT-INT-001-01, AT-INT-006-01 (labels/mode), AT-INT-sec-01 (no outbound network).
Definition of done: tests green with output recorded; endpoints visible in `/docs`; contract shapes match `docs/contracts.md`.

### TASK-025: Read-through and event inbox
Status: Planned · Priority: P2 · Phase: P3 · Links: FR-INT-002, FR-INT-003, FR-INT-005; AT-INT-002, AT-INT-003, AT-INT-005 · Depends on: TASK-024, 011, 012
Objective: Nodes read the records they cite through connectors and emit `integration_call` events (with `requestId`; not model calls); presets arrive from different systems as demo-HMAC signed webhooks; `evidenceUsed[].source` and `audit[]` populated.
Out of scope: Action Center (TASK-026).
Verification: AT-INT-002-01, AT-INT-003-01 (valid accepted, tampered rejected, ≥3 presets from ≥2 systems), AT-INT-005-01 (audit ordering).
Definition of done: stream shows integration calls with the fake model; model-call budget unchanged by connector calls.

### TASK-026: Action Center (engine)
Status: Planned · Priority: P2 · Phase: P4 · Links: FR-INT-004, FR-INT-005; AT-INT-004, AT-INT-005, AT-INT-sec-01 · Depends on: TASK-024, 007, 014
Objective: Pure ActionBuilders (messaging, email, tracker, erp, crm, docs, sheets, scheduling, esign, calendar block) produce artifacts from solver output + seed facts with **no model call**; `done.plannedActions[]` (dry run), `/api/execute` → `actions[]` with idempotency keys, `/api/outcome` → `reread[]`.
In scope: `integrations/actions/*`, execute/outcome wiring, idempotent replay, audit entries for approval and actions.
Out of scope: UI (TASK-027c); persistence of any kind.
Implementation notes: build order messaging, email, tracker, erp, crm, docs, sheets, scheduling, then esign and calendar block (cut-line order, BUILD_PLAN §6). Actions run only after the approval gate validates `approvedPlanId`.
Verification: AT-INT-004-01, AT-INT-005-01 (same key → same result), AT-INT-sec-01.
Definition of done: every artifact kind matches `docs/contracts.md`; planned and executed actions correspond one to one.

### TASK-027a/b/c: Integrations UI (Person B)
Status: Planned · Priority: P2 · Phase: P5 · Links: see register · Depends on: see register (built against mock fixtures until the engine tickets land)
- **027a** Connected Systems hub (tiles grouped by tier, persistent "Simulated connectors, demo data" badge, auth/scope/rate-limit chips, payload drawer) and the event inbox (preset cards with signed-webhook payloads, "Receive event").
- **027b** Integration-call chips in each agent step (system glyph, method, path, status, ms, request id) and source links on evidence chips.
- **027c** Action Center: dry-run grid beside the approval bar, live artifact cards after execute (rich previews: message, email draft, document, spreadsheet, calendar invite; generic card for the rest), idempotency chips, audit log drawer, "Re-read from systems" confirmation.
Out of scope: any backend change; real vendor logos.
Verification: manual keyboard/responsive/theme checklist (`docs/design.md` §10), AT-INT-006-01 labeling; mock stream exercises the failure path.
Definition of done: works in mock and live mode; Simulated labeling present everywhere.

### TASK-019: Budget cap (+ optional passcode)
Status: Planned · Priority: P1 · Phase: P6 · Links: NFR-OPS-001; AT-OPS-001 · Depends on: TASK-009
Objective: Enforce a bounded maximum of model calls per run and refuse beyond it; optionally gate the public URL with `DEMO_PASSCODE` or a light throttle.
In scope: budget decrement/refuse in the step path; config via env; honest documentation of the residual (stateless) abuse limit.
Verification: AT-OPS-001-01 (a run never exceeds the configured call budget).
Definition of done: budget enforced and tested; passcode/throttle behind config, documented as P2.

### TASK-023: Release — prod deploy, incognito smoke, submission
Status: Planned · Priority: P1 · Phase: P6 · Links: NFR-REL-002, release gate §7 · Depends on: all P1 tickets
Objective: Final production deploy; incognito end-to-end smoke of Flow A; assemble the submission package.
In scope: confirm env vars on Vercel; short `*.vercel.app` URL; repo public + `sk-` scan empty; ≤600-char summary; keep deployed through evaluation.
Verification: AT-UI-001-01 (unassisted Flow A), AT-SEC-001-01 (no key), AT-REL-002-01 (stays live); manual checklist recorded.
Definition of done: live URL works incognito; submission fields ready; no secret in repo/history.

> Remaining tickets (002, 003, 004, 005, 007, 009, 011, 012, 015–018, 020–022, 025 sub-details, 028, S1–S4) use the same template with the register's links; they are expanded at the start of their phase.

---

## 6. Git & collaboration

- **Two people in parallel (v0.3)**, PR-based: `feat/TASK-NNN-brief` off `main`; squash-merge; `TASK-NNN` in commit/PR. `main` auto-deploys, so it stays green. Track split and file ownership: §4a and `docs/BUILD_PLAN.md` v2 §4; rules §9a.
- One ticket in progress **per person**; never the same ticket or the same file as the other person. The solver (TASK-006/007) and the step contract (`docs/contracts.md`, TASK-009/010) are the shared cores — B builds against mock fixtures until the engine tickets land.
- CI (TASK-003) must pass before merge.

---

## 7. Quality gates & release criteria

- **Per-ticket:** rules §12 Definition of Done (observed `ruff`+types+`pytest` green; linked ATs passing/recorded; diff clean).
- **CI gate:** Ruff + type check + pytest on every PR.
- **P2 integration tickets (024–027c) do not gate release**; if behind, apply the cut lines in BUILD_PLAN §6 rather than slipping P1.
- **Release gate (PRD §12):** all **P1** ATs pass or have recorded honest manual verification; real-call orchestration visible; no key in client/repo; no real data; run stays within budget; live URL works incognito and stays deployed; submission package complete.
- **Rollback:** redeploy prior Vercel build (stateless; nothing to restore).

---

## 8. Traceability matrix (FR/NFR → AT → TASK)

| Requirement | Acceptance tests | Owning task(s) |
|---|---|---|
| FR-TWIN-001 | AT-TWIN-001-01 | 004, 005 |
| FR-TWIN-002 | AT-TWIN-002-01 | 015 |
| FR-TWIN-003 (P2) | — | 005, S2 |
| FR-EVENT-001 | AT-EVENT-001-01 | 010 |
| FR-EVENT-002 | AT-EVENT-002-01 | 020 |
| FR-EVENT-003 (P3) | — | S1 |
| FR-ORCH-001 | (via run) | 009 |
| FR-ORCH-002 | AT-ORCH-002-01 | 008, 010 |
| FR-ORCH-003 | AT-ORCH-003-01 | 010, 016 |
| FR-ORCH-004 | AT-ORCH-004-01 | 013 |
| FR-ORCH-005 | AT-ORCH-005-01 | 008, 020 |
| FR-IMP-001 | AT-IMP-001-01 | 006, 010 |
| FR-IMP-002 | AT-IMP-002-01 | 006, 011 |
| FR-IMP-003 | AT-IMP-003-01 | 006, 011 |
| FR-IMP-004 | (evidence in step) | 011, 016 |
| FR-PLAN-001 | AT-PLAN-001-01 | 006, 012 |
| FR-PLAN-002 | AT-PLAN-002-01 | 006, 012, 017 |
| FR-PLAN-003 | AT-PLAN-003-01 | 012, 017 |
| FR-PLAN-004 (P2) | AT-PLAN-004-01 | S3 |
| FR-VER-001/002/003 | AT-ORCH-004-01, AT-VER-003-01 | 013, 017 |
| FR-EXEC-001 | AT-EXEC-001-01 | 014, 018 |
| FR-EXEC-002 | AT-EXEC-002-01 | 007, 014 |
| FR-EXEC-003 | AT-EXEC-003-01 | 007, 014 |
| FR-EXEC-004 | AT-EXEC-004-01 | 014, 018 |
| FR-INT-001 (P2) | AT-INT-001-01, AT-INT-sec-01 | 024, 027a, 028 |
| FR-INT-002 (P2) | AT-INT-002-01 | 025, 027b |
| FR-INT-003 (P2) | AT-INT-003-01 | 025, 027a |
| FR-INT-004 (P2) | AT-INT-004-01 | 026, 027c |
| FR-INT-005 (P2) | AT-INT-005-01 | 025, 026, 027c |
| FR-INT-006 (P2) | AT-INT-006-01 | 024, 027a/b/c, 028 |
| FR-UI-001 | AT-UI-001-01 | 015, 016, 018 |
| FR-UI-002 | (comparison) | 017 |
| FR-UI-003 | (reset/re-run) | 018 |
| FR-SEC-001 | AT-SEC-001-01 | 002, 021 |
| FR-SEC-002 | AT-SEC-002-01 | 021 |
| FR-SEC-003 (P3) | — | S4 |
| NFR-PERF-001 | AT-PERF-001-01 | 010 |
| NFR-REL-001 | AT-REL-001-01 | 009, 020 |
| NFR-REL-002 | AT-REL-002-01 | 003, 023 |
| NFR-SEC-001 | AT-SEC-001-01 | 002, 021 |
| NFR-SEC-002 | AT-SEC-sec2-01 | 021 |
| NFR-OPS-001 | AT-OPS-001-01 | 019 |
| NFR-OPS-002 | (logs) | 020 |
| NFR-USE-001 | AT-USE-001-01 | 017 |
| NFR-USE-002 | AT-USE-002-01 | 022 |
| NFR-MAINT-001 | (structure) | 001 |

**No orphans:** every P1 FR/NFR has ≥1 owning task and its AT(s). P2/P3 requirements (including Domain INT, tickets 024–028) are owned by their own tasks and excluded from the release gate.

---

## 9. Risks & open issues

| ID | Risk/open | Mitigation / owner action |
|---|---|---|
| R1 | LiteLLM key/model TBD | Build solver+UI+double without it; wire real calls at TASK-010 once key arrives. |
| R2 | Vercel 5-min/stateless breaks orchestration | Streamed bounded graph in one request; approval at the request boundary → separate execute; TASK-010 front-loads it. |
| R3 | Public URL budget abuse | TASK-019 budget cap; optional passcode/throttle. |
| R4 | "Fake orchestration" perception | TASK-008/010/020 enforce + test real calls and honest failure. |
| R5 | Model asserts bad numbers | TASK-006 solver owns numbers; agents narrate only. |
| R7 | Deadline Nov 29 vs Nov 30 2:00 PM PKT | Treat Nov 30 2:00 PM PKT as working deadline; confirm; front-load P0–P2. |
| AR1 | Graph run latency too high | After TASK-010, run specialists as parallel LangGraph nodes (fan-out). |
| AR4 | `vercel.json` / `/api` routing | Confirmed in TASK-003 on first deploy. |
| AR5 | SSE streaming on Vercel Python functions | Proven in TASK-010 (first streamed run); fallback = buffered run returning the full trail. |
| AR6 | langchain/langgraph bundle vs Vercel function size limit | Measured in TASK-003 (first deploy); trim optional extras if over. |
| AR7 | `/mock/*` prefix clash/routing on Vercel | Verify on first push after TASK-024. |
| R9 | Simulated connectors read as real integrations | FR-INT-006 labeling; pitch says "designed to plug in". |
| R10 | Integration breadth competes with core Flow A | P2, after TASK-010; cut lines in BUILD_PLAN §6; B builds against mock. |
| R11 | Contract drift between the two tracks | `docs/contracts.md` frozen at C0; golden fixtures from TASK-006 at C1. |

**Scope discipline:** no build work is scheduled for excluded features; stretch tickets start only after the P1 release gate is met.
