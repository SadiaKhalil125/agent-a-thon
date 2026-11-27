# Architecture — CompanyTwin AI
Project: CompanyTwin AI (organizational digital twin)
Complexity: Standard
Status: Draft
Version: 0.1
Owner: Participant — engineering accountable
Last updated: 2026-11-27
Based on: docs/PRD.md v0.1 (Approved)

---

## 1. Drivers (goals & constraints)

**Driving requirements.** FR-ORCH-001…005 (coordinated, real, visible multi-agent run), FR-IMP/PLAN/VER/EXEC (investigate → plan → verify → approve → execute → verify), FR-TWIN (seeded connected model), FR-SEC-001/002 (server-side key, fabricated data). NFR-PERF-001 (no request > ~5 min), NFR-REL-001 (no server memory between requests), NFR-OPS-001 (bounded model spend), NFR-USE-001 (facts vs. calculations vs. predictions).

**The two constraints that shape everything.** Vercel Hobby gives (a) a ~5-minute per-request ceiling and (b) **no reliable server state between requests**. A naïve "one request runs all agents" design risks timeout and depends on in-memory run state. Therefore the architecture is built around **a client-driven loop that runs one agent step per request, carrying run state in the client**.

**The correctness constraint.** FR-PLAN-003 forbids invented numbers. Therefore **all quantitative results (completion days, deadline impact, cost) are computed by a deterministic solver from the seed data**, not by the LLM. Agents reason, choose and explain; the solver computes.

**Non-goals (architecture).** No database, no auth service, no queues/workers, no microservices, no multi-environment topology, no live integrations. These trace to PRD exclusions §4.3 and the Standard tier.

**Major tradeoffs.** Simplicity/robustness on Vercel over orchestration elegance (client loop vs. server-side agent framework); deterministic trust over "let the model do the math"; sequential steps over parallel (parallelism is an optional, bounded enhancement).

---

## 2. System View

### Logical components

```
Browser (demo UI)
  │  drives the step loop, holds RunContext (transcript + working twin state)
  ▼
FastAPI app (stateless per request)
  ├─ Routes/API            validate input, enforce step budget, shape responses
  ├─ Orchestration         step registry + sequence + RunContext schema
  ├─ Agents                role definitions, prompt builders, LiteLLM client wrapper
  └─ Twin                  seed loader, dependency graph, DETERMINISTIC solver
        │                                   │
        ▼                                   ▼
  data/seed/northstar.json (read-only)   LiteLLM gateway (external, server-side key)
```

### Request/data flow (Flow A, primary)

```
1  GET  /api/state                → seed → initial twin state (facts)
2  POST /api/event/start          → validate preset → RunContext{event, twin, transcript:[]}
3  POST /api/run/step  (repeat)   → run ONE agent (Observer→Impact→HR→Finance→Sales→Planner→Verifier)
                                     server recomputes hard facts via solver; LLM adds judgment/narrative
                                     returns step{role, evidence, output, derivedFacts, nextStepId, budget}
   (Verifier may set nextStepId back to Planner once → revised plan)       [FR-ORCH-004, FR-VER-002]
4  POST /api/execute              → requires an approved planId → solver applies plan → new twin state
5  POST /api/outcome              → solver re-checks new state vs selected plan → match/mismatch
   POST /api/reset (or client)    → discard working state, reload seed
```

The browser renders each step as it returns, producing the visible agent trail (FR-ORCH-003) and the side-by-side plan comparison (FR-UI-002).

---

## 3. Stack & Tradeoffs

| Layer | Choice | Rationale | Alternatives considered |
|---|---|---|---|
| Runtime | **Python 3.12** | Repo baseline; strong for the deterministic solver. | — |
| Web framework | **FastAPI** | Already in repo; async enables optional parallel specialist calls; Pydantic validates the RunContext/step contracts; built-in OpenAPI aids testing. | **Flask** (viable, no native async/validation) — rejected as a downgrade; **Next.js** — rejected, Python requested (PRD OQ2 closed). |
| Model access | **LiteLLM gateway via `openai` SDK**, server-side only | Mandated by rules; one provider path; capped key. | None (organizer-constrained). |
| UI | **Server-rendered HTML + vanilla JS** (extend current `templates/` + `static/`) | No build step, tiny bundle (NFR-PERF-002), fast to ship, easy to keep key out of client. | React/Next — rejected (build complexity, no benefit at this scope). |
| State store | **None (stateless)** — RunContext in the client; seed is read-only | NFR-REL-001; no persistence requirement; fabricated/ephemeral data. | DB/KV — rejected (no requirement; adds ops). |
| Deploy | **Vercel Hobby**, auto-deploy on push to `main` | Mandated. | — |

---

## 4. Modules & Responsibilities

| Module | Responsibility | Depends on | Must not |
|---|---|---|---|
| **api (routes)** | Validate requests, enforce step budget, call orchestration, shape JSON/HTML responses, health. | orchestration, twin | call LiteLLM directly; expose the key; trust client-supplied numbers. |
| **orchestration** | Define RunContext schema, the agent step registry and allowed sequence, budget counters, transition rules (incl. the single Verifier→Planner revision). | agents, twin | perform math; hold state across requests. |
| **agents** | For each role: build the prompt/input from RunContext + twin facts, call the LiteLLM wrapper, parse the model's judgment/narrative + its chosen plan option(s). | twin (read), litellm client | compute completion/cost numbers; invent facts. |
| **agents.litellm** | Thin wrapper over the `openai`-compatible client: config from env, one call, timeout, one bounded retry, structured error. | env | log secrets/payloads; retry unbounded. |
| **twin.model** | Typed entities (projects, tasks, people, skills, availability, milestones, customers, invoices, budget, contractor) and the dependency graph. | seed loader | depend on agents/api. |
| **twin.solver** | **Deterministic engine**: schedule tasks under an assignment, compute completion day, deadline impact, incremental cost, milestone/invoice eligibility; generate candidate recovery options; apply an approved plan; verify outcome. Pure functions. | twin.model | call the model; have side effects outside returned state. |
| **twin.seed** | Load and validate `data/seed/northstar.json` into the model. | — | contain secrets or real data. |
| **UI (templates/static)** | Drive the step loop, render the agent trail, plan comparison, approval, outcome, reset. | api | contain the key or model-call logic. |

Dependency direction: `api → orchestration → {agents, twin}`, `agents → twin(read)`. `twin.solver` is a pure leaf. No circular dependencies.

---

## 5. Proposed Folder Structure

```
agent-a-thon/
├─ app.py                     [EXISTING — to be refactored: mount routers, keep render_index]
├─ branding.py                [EXISTING — rebrand to CompanyTwin]
├─ requirements.txt           [EXISTING — add deps as needed]
├─ vercel.json                [PROPOSED — explicit FastAPI build/routes if needed]
├─ api/                       [PROPOSED]
│  ├─ state.py                   GET /api/state, /api/health
│  ├─ run.py                     POST /api/event/start, /api/run/step
│  └─ execute.py                 POST /api/execute, /api/outcome, /api/reset
├─ orchestration/             [PROPOSED]
│  ├─ context.py                 RunContext pydantic schema
│  ├─ registry.py                step order, transitions, budget
│  └─ budget.py                  per-run call cap enforcement
├─ agents/                    [PROPOSED]
│  ├─ base.py                    prompt-build + parse scaffolding
│  ├─ roles.py                   role definitions/system prompts
│  └─ litellm_client.py          server-side gateway wrapper
├─ twin/                      [PROPOSED]
│  ├─ model.py                   entities + dependency graph
│  ├─ solver.py                  deterministic scheduler/cost/outcome
│  └─ seed.py                    loader + validation
├─ data/seed/
│  └─ northstar.json          [PROPOSED — fabricated company]
├─ templates/
│  └─ index.html              [EXISTING — replace single-prompt UI with demo flow]
├─ static/
│  ├─ css/main.css            [EXISTING — extend]
│  └─ js/                     [EXISTING theme.js; chat.js REPLACED by run.js/state.js/plans.js]
├─ tests/                     [PROPOSED]
│  ├─ test_solver.py             unit (deterministic math)
│  ├─ test_run_steps.py          integration (steps, budget, failure, approval gate)
│  └─ test_security.py           repo/key scan
└─ docs/                      [EXISTING — PRD.md, architecture.md, …]
```

Existing single-prompt `/api/chat` + `chat.js` are **replaced**, not extended.

---

## 6. Data & State

- **Seed (read-only, committed).** `data/seed/northstar.json` holds the fabricated model. Validated on load (every invoice → a milestone; every milestone → ≥1 task; availability windows well-formed). This is the single source of hard facts.
- **RunContext (ephemeral, client-held).** `{ runId, event, workingTwin, transcript[], budget, approvedPlanId? }`. Sent with each `/api/run/step`. Bounded well under 4.5 MB (NFR-PERF-002).
- **Trust rule.** The server **recomputes** all derived facts from the seed + event + candidate plan each step via the solver; it does **not** trust numbers in the client transcript. Model-generated *narrative* is passed through for display and as context to the next agent.
- **Working twin & execution.** `/api/execute` applies the approved plan to a working copy via the solver and returns the new state; the client holds it. **Reset** reloads the seed. No persistence; nothing shared between users or requests (NFR-REL-001).
- **Acknowledged limitation.** Because the transcript is client-carried, a determined user could alter prior *narrative*. Numbers are protected (server-recomputed); narrative tampering only affects that user's own demo and cannot exceed the call budget. Documented, accepted for a fabricated-data demo.

---

## 7. API / Interface Contracts

| Endpoint | In | Out | Notes |
|---|---|---|---|
| `GET /api/health` | — | `{ok, litellm_configured}` | existing, kept. |
| `GET /api/state` | — | initial twin state (facts) | from seed. |
| `POST /api/event/start` | `{presetId}` | `{runId, event, twin, firstStepId, budget}` | validate `presetId ∈ presets`. |
| `POST /api/run/step` | `{runId, stepId, event, transcript, workingTwin}` | `{stepId, role, evidenceUsed[], output, derivedFacts, plans?, verdict?, nextStepId|null, budget}` | **exactly one** model call; server recomputes `derivedFacts`/`plans` via solver. |
| `POST /api/execute` | `{runId, approvedPlanId, workingTwin}` | `{twin, applied:true}` | **requires** a plan id produced in this run (FR-EXEC-001). |
| `POST /api/outcome` | `{runId, approvedPlanId, workingTwin}` | `{match:bool, expected, actual, deltas[]}` | solver re-check. |
| `POST /api/reset` | `{runId}` | initial state | client may also reset locally. |

**Validation & errors.** All bodies validated by Pydantic. Error shape `{error, code}` with safe generic messages (NFR-SEC-002); unknown preset/step/plan → 400; gateway/config problems → 503/500 without leaking internals. **Idempotency:** steps are pure given identical input (seeded), so a retried POST reproduces the same result; no dedup store needed. **Versioning:** single internal API, no external consumers; not versioned.

---

## 8. Security Boundaries

- **Secret handling (FR-SEC-001, NFR-SEC-001).** `LITELLM_API_KEY/BASE_URL/MODEL` read from env server-side only; `.env.local` gitignored; never sent to the browser, logged, or committed. Only `/api/health` exposes a boolean `litellm_configured`.
- **Trust boundaries.** Two untrusted inputs: the browser (request bodies) and the LiteLLM response (treated as text, never executed; parsed defensively). Validate `presetId`, `stepId`, `approvedPlanId`, and bound `transcript`/`workingTwin` size.
- **Authorization.** None by design (single public demo workspace, PRD §4.3). The only guarded action — applying state changes — is gated on an **in-run approved plan id**, not on identity.
- **Least privilege / data.** No DB, no PII, fabricated data only (FR-SEC-002); the app makes exactly one outbound destination — the LiteLLM gateway.
- **Abuse/budget (NFR-OPS-001).** See §9; the public URL + capped key is the main residual security/cost risk.

---

## 9. Failure Behavior

| Failure | Handling |
|---|---|
| LiteLLM timeout/5xx | One bounded retry in the wrapper, then the step returns `status:"failed"`; UI marks it failed/unavailable; **no fabricated output** (FR-ORCH-005). Safe generic message to client; provider error logged server-side without secrets. |
| Not configured | `/api/run/step` returns 503 with the "configure LiteLLM" guidance (existing pattern). |
| Request near 5-min cap | Each request is a single agent call, well under the cap (NFR-PERF-001); no server-side multi-agent chain in one request. |
| Model returns an unparseable/implausible plan choice | Parser falls back to the solver's deterministic candidate set; the model's free text is still shown; numbers stay solver-authoritative. |
| Budget exhausted | `budget.remaining == 0` → further steps refused with a clear message (FR-ORCH / NFR-OPS). |
| **Abuse of public URL** | Residual risk. Mitigations: hard cap of one model call per request; fixed max steps per run enforced server-side per `runId` within the request budget field; **optional** lightweight per-IP throttle or a shared passcode as a stretch (NFR-OPS-001, PRD OQ4). Honest limitation: without server state, a scripted caller could start many runs — the passcode/throttle is the real cap and is the recommended P2 hardening. |
| Reset mid-run | Discards working state; no external effect (FR-EXEC-004). |

Rollback/compensation: not applicable — execution only mutates the client's working twin, which reset restores; nothing external to undo.

---

## 10. Deployment & Configuration

- **Platform:** Vercel Hobby, Python/FastAPI preset; production domain `https://<project>.vercel.app`; auto-deploy on push to `main`.
- **Config:** env vars `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `LITELLM_MODEL` (Vercel project settings + local `.env.local`). Optional `DEMO_PASSCODE`, `MAX_CALLS_PER_RUN` (P2).
- **Build:** `requirements.txt`; add `vercel.json` only if the default FastAPI detection needs explicit routing for `/api/*` + static. No DB, no migrations.
- **Secrets:** stored only in Vercel env / local `.env.local`; rotation = update env + redeploy (per DEPLOYMENT.md).
- **Rollback/recovery:** redeploy a previous Vercel deployment; app is stateless so recovery is immediate; no data to restore.

---

## 11. Observability & Operations

- **Structured logs** per run/step: `runId`, `stepId`, `role`, duration ms, provider status, model-call count, budget remaining. **Never** log the key, prompts' sensitive content (none here), or full payloads (NFR-OPS-002).
- **Health:** `/api/health` → `{ok, litellm_configured}` for a quick liveness/config check.
- **Alerting:** none required at this tier; Vercel deploy status + logs suffice.
- **Support owner:** the participant (single-owner project).

---

## 12. Test Approach

| Layer | What | Real vs. mock |
|---|---|---|
| **Unit** | `twin.solver` — scheduling, completion day, deadline impact, incremental cost, milestone/invoice eligibility, outcome check. Highest value; fully deterministic. | Real, no model. |
| **Integration** | `/api/run/step` sequence; budget cap; approval gate (no execute without approved plan); honest failure on gateway error; reset/no-external-call; deterministic re-run. | **LiteLLM wrapper injected with a test double** that (a) asserts a call occurred (AT-ORCH-002-01) and (b) can simulate failure (AT-ORCH-005-01). |
| **E2E / smoke** | Happy path through the client loop (served HTML + step endpoints). | Test double or a single cheap real call in a smoke run. |
| **Security** | Repo/bundle/network scan for the key and `sk-`; real-data review. | Static scan + manual. |

Contract checks: Pydantic schemas on every request/response are the enforced contract; tests assert the step response shape and the plan-comparison fields.

---

## 13. Decisions & Risks

### Architecture decisions (ADRs)

- **ADR-001 — Deterministic solver owns all numbers; LLM agents reason/explain only.** Guarantees FR-PLAN-003 (no invented figures), makes results testable without the model, and keeps the demo correct and repeatable. The model chooses among and narrates solver-produced options.
- **ADR-002 — Client-driven step loop; one agent/model call per request; state in client RunContext.** Satisfies NFR-PERF-001 (no long request) and NFR-REL-001 (no server memory) directly, and yields the visible ordered trail (FR-ORCH-003) and bounded calls (NFR-OPS-001) as a by-product. Server-side streaming of a single run is noted as an alternative if step-loop latency feels high, but carries the 5-min risk; not chosen by default.
- **ADR-003 — FastAPI (Python).** Repo baseline; async supports optional parallel specialists; Pydantic/OpenAPI aid contracts and testing. Flask is a viable Python alternative but lacks native async/validation; Next.js excluded per the Python decision. Closes PRD OQ2.
- **ADR-004 — No database; in-session working state only.** No persistence requirement; fabricated/ephemeral data; reset reloads seed. Avoids unjustified infrastructure (Complexity Policy §3).

### Implemented agent roster (resolves the open "how many agents" question)

For the **primary recovery scenario**, implement **8 model-backed agent steps** plus an **Orchestrator** realized as the registry/sequence (control logic, not necessarily its own model call):

`Observer → Impact Investigator → HR/Resource → Finance → Sales → Planner → Verifier (→ Planner revise once) → Execution`.

Operations/Procurement from the conceptual roster is **excluded from the primary scenario** (it belongs to a supplier-type event, a P2 second scenario). This comfortably exceeds G1's "≥3 roles with handoffs + a rejecting verifier." Whether to **merge** the four specialists (HR/Finance/Sales/Delivery) behind one parallel `asyncio.gather` request to cut latency is a bounded implementation choice recorded for the design/phases stage; the default is distinct sequential steps for maximum visible orchestration.

### Open items carried forward

| ID | Item | Where resolved |
|---|---|---|
| AR1 | Exact step latency acceptable? If too slow, consider parallel specialists or server streaming (ADR-002 alt). | Design/Phases, after a first real run. |
| AR2 | Passcode/throttle for the public URL. | Phases (P2 hardening), PRD OQ4. |
| AR3 | Solver scope: does the primary preset need a full scheduler or a small fixed calculator for the known chain? | Design; start minimal, expand only if a second scenario is added. |
| AR4 | `vercel.json` needed, or does default detection route `/api/*` + static correctly? | Phases setup ticket (verify on first deploy). |

### Consistency with PRD
No new scope introduced; every module serves a PRD requirement; no microservices/DB/queue/cache; auth intentionally absent per PRD §4.3; failure and budget behavior realize NFR-REL/OPS. No PRD change requests arise from this architecture.
