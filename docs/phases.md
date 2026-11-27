# Phases & Tickets — CompanyTwin AI
Project: CompanyTwin AI (organizational digital twin)
Complexity: Standard
Status: Draft
Version: 0.1
Owner: Participant
Last updated: 2026-11-27
Based on: docs/PRD.md v0.1, docs/architecture.md v0.1, docs/design.md v0.1, docs/rules.md v0.1 (all Approved)

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
| **P2 Core agent slice** | One agent step end-to-end (event → step → visible result) with a **real** model call, stateless, budgeted. | Impact step runs on Vercel, visible, within budget; failure handled honestly. |
| **P3 Full orchestration** | Remaining agents, handoffs, planner (≥2 plans), verifier reject→revise. | Full trail runs; a rejection produces a revised plan. |
| **P4 Execution loop** | Approval gate, execute, outcome verification, reset. | No change without approval; outcome reports match/mismatch; reset restores seed. |
| **P5 UI build-out** | Full demo flow, agent trail, plan comparison, fact tags, states. | Flow A completable unaided; all design states present. |
| **P6 Hardening & release** | Budget cap, honest failure/not-configured, security scan, a11y/responsive, prod deploy + submission. | All P1 ATs pass/recorded; incognito smoke clean; submission package ready. |

---

## 3. Dependency plan

- **Critical prerequisites:** LiteLLM key (external, organizer) — blocks real-call tests in P2+ but **not** P0/P1 (solver + UI shell build without it; use the test double). Vercel project + GitHub repo (P0).
- **Risky integration tested early:** TASK-003 (skeleton deploy) and TASK-010 (first real agent call on Vercel) front-load the two platform risks (deploy config, 5-min/stateless real call).
- **Sequence rationale:** deterministic solver (P1) before agents (P2/P3) so agent output has trustworthy numbers to narrate (ADR-001); execution (P4) after plans exist; UI (P5) after the API contract is stable; hardening/release (P6) last.
- **External blockers:** model id/gateway TBD (R1); deadline (R7).

---

## 4. Ticket register

| ID | Title | Phase | Pri | Status | Depends on | Links (FR / NFR / AT) |
|---|---|---|---|---|---|---|
| TASK-001 | Scaffold, tooling & module skeleton | P0 | P1 | Planned | — | rules §2/§8; NFR-MAINT-001 |
| TASK-002 | Rebrand to CompanyTwin + health | P0 | P1 | Planned | 001 | FR-SEC-001; AT-SEC-001-01 |
| TASK-003 | Early Vercel skeleton deploy + CI | P0 | P1 | Planned | 001,002 | NFR-REL-002; AT-REL-002-01 |
| TASK-004 | Seed data `northstar.json` + loader/validation | P1 | P1 | Planned | 001 | FR-TWIN-001; AT-TWIN-001-01 |
| TASK-005 | Twin model + dependency graph | P1 | P1 | Planned | 004 | FR-TWIN-001/003 |
| TASK-006 | Solver: schedule / completion / cost / eligibility + candidate plans | P1 | P1 | Planned | 005 | FR-IMP-001/003, FR-PLAN-001/002/003; AT-IMP-001/003, AT-PLAN-001/002 |
| TASK-007 | Solver: apply plan + outcome verification | P1 | P1 | Planned | 006 | FR-EXEC-002/003; AT-EXEC-002/003 |
| TASK-008 | LiteLLM wrapper (retry/timeout/error + test double) | P0/P2 | P1 | Planned | 001 | FR-ORCH-002/005; AT-ORCH-002/005 |
| TASK-009 | RunContext schema + orchestration registry + budget | P2 | P1 | Planned | 005,008 | FR-ORCH-001, NFR-OPS-001, NFR-REL-001; AT-OPS-001, AT-REL-001 |
| TASK-010 | **Core slice:** event/start + run/step (Impact) end-to-end on Vercel | P2 | P1 | Planned | 006,009 | FR-EVENT-001, FR-ORCH-002/003, FR-IMP-001; AT-EVENT-001, AT-ORCH-002/003, AT-IMP-001, AT-PERF-001 |
| TASK-011 | Remaining investigation agents (Observer, HR, Finance, Sales) | P3 | P1 | Planned | 010 | FR-IMP-002/003/004; AT-IMP-002/003 |
| TASK-012 | Planner step → ≥2 plans from solver candidates | P3 | P1 | Planned | 010,006 | FR-PLAN-001/002/003; AT-PLAN-001/002/003 |
| TASK-013 | Verifier step + reject→revise transition | P3 | P1 | Planned | 012 | FR-VER-001/002/003, FR-ORCH-004; AT-ORCH-004, AT-VER-003 |
| TASK-014 | Approval gate + execute + outcome endpoints | P4 | P1 | Planned | 007,013 | FR-EXEC-001/002/003/004; AT-EXEC-001/002/003/004 |
| TASK-015 | UI: company state §1 + dependency chain | P5 | P1 | Planned | 004,010 | FR-TWIN-002, FR-UI-001; AT-TWIN-002 |
| TASK-016 | UI: agent trail + step states (incl. failed) | P5 | P1 | Planned | 010,013 | FR-ORCH-003/005, FR-UI-001; AT-ORCH-003/005 |
| TASK-017 | UI: plan comparison + verdict + fact tags | P5 | P1 | Planned | 012,013 | FR-UI-002, FR-PLAN-002, FR-VER-003, NFR-USE-001; AT-USE-001 |
| TASK-018 | UI: approval bar + outcome + reset + progress rail | P5 | P1 | Planned | 014 | FR-EXEC-001, FR-UI-001/003; AT-UI-001 |
| TASK-019 | Hardening: budget cap enforcement (+ optional passcode) | P6 | P1 | Planned | 009 | NFR-OPS-001; AT-OPS-001 |
| TASK-020 | Honest failure + not-configured + deterministic re-run | P6 | P1 | Planned | 010,008 | FR-ORCH-005, NFR-REL-001, FR-EVENT-002; AT-ORCH-005, AT-EVENT-002, AT-REL-001 |
| TASK-021 | Security: key/data scan + input-validation negatives | P6 | P1 | Planned | 014 | FR-SEC-001/002, NFR-SEC-002; AT-SEC-001/002 |
| TASK-022 | Accessibility + responsive pass | P6 | P1 | Planned | 015-018 | NFR-USE-002; AT-USE-002 |
| TASK-023 | Release: prod deploy, incognito smoke, submission package | P6 | P1 | Planned | all P1 | NFR-REL-002; release gate §7 |
| TASK-S1 | (Stretch) Custom event params | — | P3 | Planned | 010 | FR-EVENT-003 |
| TASK-S2 | (Stretch) Relationship graph view | — | P3 | Planned | 015 | FR-TWIN-003 |
| TASK-S3 | (Stretch) Constraint-conflict 2nd scenario | — | P2 | Planned | 012 | FR-PLAN-004; AT-PLAN-004 |
| TASK-S4 | (Stretch) Synthetic permission demo | — | P3 | Planned | 015 | FR-SEC-003 |

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

### TASK-008: LiteLLM wrapper
Status: Planned · Priority: P1 · Phase: P0/P2 · Links: FR-ORCH-002/005; AT-ORCH-002/005 · Depends on: TASK-001
Objective: A server-side `openai`-compatible wrapper: config from env, one call, timeout, **one** bounded retry, structured error; and an injectable **test double**.
In scope: the wrapper + error taxonomy mapping (rules §6); test double that asserts a call occurred and can simulate failure.
Out of scope: prompts/roles (TASK-010/011); budget counting (TASK-009).
Affected files: `agents/litellm_client.py`, `tests/` helpers.
Implementation notes: never log key/payload; retry at most once; raise `UpstreamModelError` on failure (no fabricated content).
Verification: integration test proves a call happens (AT-ORCH-002-01) and that a simulated failure surfaces as a failed step with no content (AT-ORCH-005-01) — using the double, no paid call.
Definition of done: wrapper + double tested green; key never logged (asserted).

### TASK-010: Core agent slice end-to-end (the de-risk ticket)
Status: Planned · Priority: P1 · Phase: P2 · Links: FR-EVENT-001, FR-ORCH-002/003, FR-IMP-001; AT-EVENT-001, AT-ORCH-002/003, AT-IMP-001, AT-PERF-001 · Depends on: TASK-006, TASK-009
Objective: One real agent step working end-to-end **on Vercel**: `POST /api/event/start` → `POST /api/run/step` (Impact Investigator) → visible result, stateless, within budget and the 5-min ceiling.
In scope: the two endpoints for a single step; RunContext round-trip (client-carried); minimal trail rendering; a real LiteLLM call behind the step; solver supplies the facts the agent narrates.
Out of scope: other agents, plans, verifier, execution, full UI.
Affected files: `api/run.py`, `orchestration/*`, `agents/base.py`+`roles.py` (Impact only), `templates/index.html`+`static/js/run.js`.
Implementation notes: exactly one model call per request; recompute facts server-side; prove no server-memory dependence.
Verification: AT-EVENT-001-01 (preset starts run), AT-ORCH-002-01 (real call), AT-ORCH-003-01 (ordered visible step), AT-IMP-001-01 (full chain), AT-PERF-001-01 (request < 5 min); deployed and exercised on the Vercel URL.
Definition of done: the slice runs on production URL with evidence; honest failure path present (ties to TASK-020).

### TASK-013: Verifier + reject→revise
Status: Planned · Priority: P1 · Phase: P3 · Links: FR-VER-001/002/003, FR-ORCH-004; AT-ORCH-004, AT-VER-003 · Depends on: TASK-012
Objective: A Verifier step that can reject an infeasible/unsupported plan with a reason, driving a single revised Planner output that addresses the objection.
In scope: verifier role + the one-time Planner→Verifier→Planner transition in the registry; a seeded rejectable candidate for deterministic testing.
Out of scope: unbounded revise loops (cap = 1).
Affected files: `agents/roles.py`, `orchestration/registry.py`, tests.
Verification: AT-ORCH-004-01 (rejection changes the plan, references objection), AT-VER-003-01 (verdict+reason visible).
Definition of done: rejection→revision demonstrated deterministically; verdict surfaced to UI contract.

### TASK-014: Approval gate + execute + outcome
Status: Planned · Priority: P1 · Phase: P4 · Links: FR-EXEC-001/002/003/004; AT-EXEC-001/002/003/004 · Depends on: TASK-007, TASK-013
Objective: `/api/execute` (requires in-run `approvedPlanId`) applies the plan via the solver; `/api/outcome` re-checks vs the selected plan; `/api/reset` restores seed.
In scope: the approval-gated execution, outcome verification, reset; no external calls during execution.
Out of scope: UI (TASK-018).
Affected files: `api/execute.py`, `twin/solver.py` (apply/outcome from TASK-007), tests.
Verification: AT-EXEC-001 (no change without approval), AT-EXEC-002 (applied), AT-EXEC-003 (match/mismatch), AT-EXEC-004 (reset + no external call).
Definition of done: all four EXEC ATs green; approval gate proven server-side.

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

> Remaining tickets (002, 003, 004, 005, 007, 009, 011, 012, 015–018, 020–022, S1–S4) use the same template with the register's links; they are expanded at the start of their phase.

---

## 6. Git & collaboration

- Solo developer, but PR-based: `feat/TASK-NNN-brief` off `main`; squash-merge; `TASK-NNN` in commit/PR. `main` auto-deploys, so it stays green.
- One ticket in progress at a time; no parallel edits to the same module. The solver (TASK-006/007) and the step contract (TASK-009/010) are the shared cores — stabilize them before dependent UI tickets.
- CI (TASK-003) must pass before merge.

---

## 7. Quality gates & release criteria

- **Per-ticket:** rules §12 Definition of Done (observed `ruff`+types+`pytest` green; linked ATs passing/recorded; diff clean).
- **CI gate:** Ruff + type check + pytest on every PR.
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

**No orphans:** every P1 FR/NFR has ≥1 owning task and its AT(s). P2/P3 requirements are owned by stretch tasks and excluded from the release gate.

---

## 9. Risks & open issues

| ID | Risk/open | Mitigation / owner action |
|---|---|---|
| R1 | LiteLLM key/model TBD | Build solver+UI+double without it; wire real calls at TASK-010 once key arrives. |
| R2 | Vercel 5-min/stateless breaks orchestration | TASK-003 + TASK-010 front-load the risk; one call/request; client-carried state. |
| R3 | Public URL budget abuse | TASK-019 budget cap; optional passcode/throttle. |
| R4 | "Fake orchestration" perception | TASK-008/010/020 enforce + test real calls and honest failure. |
| R5 | Model asserts bad numbers | TASK-006 solver owns numbers; agents narrate only. |
| R7 | Deadline Nov 29 vs Nov 30 2:00 PM PKT | Treat Nov 30 2:00 PM PKT as working deadline; confirm; front-load P0–P2. |
| AR1 | Step latency too high | After TASK-010, consider parallel specialists / streaming (architecture ADR-002 alt). |
| AR4 | `vercel.json` needed? | Confirmed in TASK-003 on first deploy. |

**Scope discipline:** no build work is scheduled for excluded features; stretch tickets start only after the P1 release gate is met.
