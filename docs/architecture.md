# Architecture — CompanyTwin AI
Project: CompanyTwin AI (organizational digital twin)
Complexity: Standard
Status: Draft
Version: 0.3
Owner: Participant — engineering accountable
Last updated: 2026-11-28
Based on: docs/PRD.md v0.2 (owner-approved scope change: simulated connectors)

> **Change record (v0.2 → v0.3, 2026-11-28):** adds the `integrations/` module (simulated enterprise connectors, Connector + manifest + ActionBuilder), the `/mock/*` and `/api/integrations` surface, new SSE/response fields (`integration_call`, `plannedActions`, `actions`, `audit`, `reread`) and **ADR-005**. Implements PRD v0.2 Domain INT (FR-INT-001…006, P2). The API contract is frozen in `docs/contracts.md`. No change to ADR-001…004.

> **Change record (v0.1 → v0.2, approved 2026-11-28):** Adopt **LangGraph** for multi-agent orchestration (reverses ADR-003, which had chosen plain Python) and revise ADR-002 accordingly. No PRD requirement changes — LangGraph is a mechanism; all FR/NFR/AC/AT keep their meaning and IDs. Deterministic solver (ADR-001) is unchanged: graph nodes call it as plain functions.

---

## 1. Drivers (goals & constraints)

**Driving requirements.** FR-ORCH-001…005 (coordinated, real, visible multi-agent run), FR-IMP/PLAN/VER/EXEC (investigate → plan → verify → approve → execute → verify), FR-TWIN (seeded connected model), FR-SEC-001/002 (server-side key, fabricated data). NFR-PERF-001 (no request > ~5 min), NFR-REL-001 (no server memory between requests), NFR-OPS-001 (bounded model spend), NFR-USE-001 (facts vs. calculations vs. predictions).

**The platform constraints.** Vercel Hobby gives a ~5-minute per-request ceiling and no reliable server state between requests. **The orchestration is a LangGraph `StateGraph` run server-side.** The investigation→plan→verify graph executes in **one streamed request** that emits a per-node event for the live agent trail; the **human-approval gate sits at the request boundary** — a separate `/api/execute` request applies the approved plan. So no LangGraph state needs to persist between requests (each request is self-contained), and the only long-running request is the streamed graph run, kept under the ceiling by a bounded node budget and optional parallel specialist nodes.

**The correctness constraint.** FR-PLAN-003 forbids invented numbers. **All quantitative results are computed by the deterministic `twin.solver` from the seed**, not by the LLM. Graph nodes reason, choose and explain; they call the solver for every number (ADR-001).

**Non-goals (architecture).** No database, no auth service, no queues/workers, no microservices, no multi-environment topology, no **real** integrations (PRD §4.3; simulated in-process connectors are in scope, see ADR-005).

**Major tradeoffs.** A real orchestration graph (LangGraph) over hand-rolled control flow — clearer multi-agent story, native conditional edges and parallel fan-out — accepting a heavier dependency and a single streamed run to manage against the 5-min ceiling. Deterministic trust over "let the model do the math."

---

## 2. System View

### Logical components

```
Browser (demo UI)
  │  POST /api/run/stream {presetId}  → consumes SSE node events, renders the live trail
  │  POST /api/execute {approvedPlanId} after the human approves
  ▼
FastAPI app (stateless per request)
  ├─ Routes/API            validate input, stream node events, shape responses
  ├─ Orchestration         LangGraph StateGraph: nodes, edges, conditional verifier→planner edge, node budget
  ├─ Agents                graph nodes (role prompt builders) + ChatOpenAI→LiteLLM factory
  ├─ Integrations (v0.3)   SIMULATED connectors: Connector + manifest + registry; read adapters; ActionBuilders (in-process, no network)
  └─ Twin                  seed loader, dependency graph, DETERMINISTIC solver (called by nodes)
        │                                   │
        ▼                                   ▼
  data/seed/northstar.json (read-only)   LiteLLM gateway (external, server-side key, via LangChain ChatOpenAI)
```

`/mock/*` mounts the same connector handlers over HTTP (OpenAPI tag "Simulated connectors") so the endpoints are inspectable; nodes call them **in-process**, not over HTTP.

### The graph (Flow A, primary)

```
START
  → observer/impact_node ──► specialists (HR ∥ Finance ∥ Sales, parallel fan-out) ──► planner_node
                                                                                        │
                                                                        verifier_node ◄─┘
                                                                        │   conditional edge:
                                                                        │   reject → planner_node (once)
                                                                        │   approve → END (emit verified plans)
```

Each node = one LLM call (via ChatOpenAI→LiteLLM) + solver-computed facts. The graph streams a node event as each finishes, producing the visible ordered trail (FR-ORCH-003) and the plan comparison (FR-UI-002). After `END`, the browser shows the plans; **the human approves; `/api/execute` (a separate request) applies the plan via the solver and verifies the outcome.**

---

## 3. Stack & Tradeoffs

| Layer | Choice | Rationale | Alternatives considered |
|---|---|---|---|
| Runtime | **Python 3.11+** | Repo baseline (local 3.11.9; Vercel can run 3.12). | — |
| Web framework | **FastAPI** | Async suits streaming (SSE) and parallel nodes; Pydantic validates request contracts. | Flask (no native async/streaming ergonomics) — rejected. |
| **Orchestration** | **LangGraph** (`langgraph==1.2.24`) | A real multi-agent graph: explicit nodes, handoffs, a **conditional edge** for verifier→planner revision, and **parallel fan-out** for specialists. Allowed by the hackathon guide; a strong, legible orchestration artifact for judges. | Plain-Python registry (prior ADR-003) — reversed by owner decision; frameworks like CrewAI/AutoGen — not chosen. |
| Model access | **LangChain `ChatOpenAI`** (`langchain-openai==1.8.5`) pointed at **any OpenAI-compatible gateway**, server-side only; endpoint configured in the environment, the LiteLLM gateway for submission | `ChatOpenAI(base_url, api_key, model)` from `config.get_llm_settings()`; provider-neutral env vars `LLM_*` (legacy `LITELLM_*` accepted as fallback). Key never leaves the server. | Raw `openai` SDK — still present transitively; LangChain chosen to integrate with LangGraph nodes. |
| UI | **Server-rendered HTML + vanilla JS** consuming **SSE** | No build step, tiny bundle; `EventSource`/fetch-stream renders the trail live. | React/Next — rejected (build complexity). |
| State store | **None (stateless)** — each request self-contained; seed read-only | NFR-REL-001; graph state lives in memory only for the single streamed run. | DB/KV — rejected (no requirement). |
| Deploy | **Vercel Hobby**, auto-deploy on push to `main` | Mandated. | — |

Bundle note: the langgraph + langchain stack is pure-Python but non-trivial; **must verify the deployed function stays within Vercel's size limit** (AR6).

---

## 4. Modules & Responsibilities

| Module | Responsibility | Depends on | Must not |
|---|---|---|---|
| **api (routes)** | Validate requests, run the graph and **stream node events**, shape execute/outcome responses, health. | orchestration, twin | call the model directly; expose the key; trust client-supplied numbers. |
| **orchestration** | Build the LangGraph `StateGraph` (`graph.py`): register nodes, wire edges incl. the conditional verifier→planner edge, enforce the per-run **node/call budget**; define the graph **State** (`state.py`). | agents, twin | perform math; hold state across requests. |
| **agents** | Graph **nodes** (`nodes.py`) — one per role; each builds its prompt from the graph State + solver facts (`roles.py`), invokes the chat model, parses judgment/narrative + chosen option. `llm.py` is the **ChatOpenAI→LiteLLM factory**. | twin (read), langchain-openai | compute numbers; invent facts; log the key. |
| **integrations** (v0.3) | Simulated enterprise systems: a `Connector` base (read/write/webhook/artifact capabilities) with a per-system **manifest** (category, tier, auth mode, scopes, rate limit); a registry; **read adapters** (hris, tracker, erp, crm, calendar) as pure views over the seed; **ActionBuilders** (`integrations/actions/*`) that turn solver output + seed facts into artifacts (message, email draft, document, spreadsheet, calendar event, e-sign, ticket update, purchase order, CRM note, calendar block); demo HMAC webhook verification; idempotency keys; audit entries. | twin (read) | call the model; compute numbers; make any outbound network call; persist state; use real credentials. |
| **twin.solver** | **Deterministic engine**: schedule, completion day, deadline impact, incremental cost, eligibility; candidate plans; apply approved plan; verify outcome. Pure functions, **called by nodes as tools**. | twin.model | call the model; side effects. |
| **twin.model / twin.seed** | Entities + dependency graph; load/validate `northstar.json`. | — | contain secrets or real data. |
| **UI (templates/static)** | Start a run, consume SSE, render trail + plan comparison + approval + outcome + reset. | api | contain the key or model-call logic. |

Dependency direction: `api → orchestration → {agents, integrations, twin}`, `agents → {integrations, twin}(read)`, `integrations → twin(read)`. `twin.solver` is a pure leaf. No circular dependencies.

---

## 5. Proposed Folder Structure

```
agent-a-thon/
├─ app.py                     [EXISTING — refactor: mount routers, keep render_index]
├─ branding.py                [EXISTING — rebrand]
├─ requirements.txt           [EXISTING — pinned; + langgraph, langchain-openai]
├─ vercel.json                [PROPOSED — add only once first deploy confirms what's needed (AR4)]
├─ api/                       [PROPOSED]
│  ├─ state.py                   GET /api/state, /api/health
│  ├─ run.py                     POST /api/run/stream  (SSE: runs the graph, emits node events)
│  ├─ execute.py                 POST /api/execute, /api/outcome, /api/reset
│  └─ integrations.py            GET /api/integrations(+/{id}/sample); mounts /mock/* (v0.3)
├─ integrations/              [PROPOSED v0.3 — TASK-024..026, 028]
│  ├─ base.py · manifest.py · registry.py          Connector base, manifests, registry
│  ├─ hris.py · tracker.py · erp.py · crm.py · calendar.py   tier-1 read adapters (views over seed)
│  └─ actions/ (messaging, email, docs, sheets, scheduling, esign, tracker, erp, crm)   ActionBuilders
├─ orchestration/             [PROPOSED]
│  ├─ state.py                   LangGraph graph State (messages/transcript, event, plans, verdict, budget)
│  ├─ graph.py                   build_graph(): nodes, edges, conditional verifier→planner edge
│  └─ budget.py                  per-run node/call budget
├─ agents/                    [PROPOSED]
│  ├─ llm.py                     ChatOpenAI factory (base_url/api_key/model from env) → LiteLLM
│  ├─ nodes.py                   the role node functions used by the graph
│  └─ roles.py                   role system prompts + input builders
├─ twin/                      [PROPOSED]
│  ├─ model.py · solver.py · seed.py   deterministic core (called by nodes)
├─ data/seed/northstar.json   [PROPOSED — TASK-004]
├─ templates/index.html       [EXISTING — replace single-prompt UI]
├─ static/ (css/main.css, js/{theme.js, run.js, api-client.js, integrations.js}, mock/*.json)  [chat.js REPLACED by run.js (SSE); api-client.js = live/mock switch]
├─ tests/ (test_solver.py, test_graph.py, test_security.py, test_integrations.py; ui/)   [PROPOSED]
└─ docs/ · AGENTS.md          [EXISTING]
```

> Scaffold note: TASK-001 created `agents/litellm_client.py`, `orchestration/context.py`, `orchestration/registry.py`. Under v0.2 these become `agents/llm.py`, `orchestration/state.py`, `orchestration/graph.py` — renamed when TASK-008/009 land.

---

## 6. Data & State

- **Seed (read-only, committed).** `data/seed/northstar.json`, validated on load. Single source of hard facts.
- **Run state (ephemeral, in-memory for one streamed request).** The LangGraph **State** object holds the event, accumulating node outputs/transcript, the solver-derived facts, candidate plans and the verifier verdict. It exists only for the duration of the single `/api/run/stream` invocation — which is permitted, since it is one request (NFR-REL-001 forbids reliance on memory *between* requests, not within one).
- **Approval at the request boundary.** The graph run ends by emitting verified plans. The human approves client-side. `/api/execute` is a **separate, self-contained request** carrying `{presetId, approvedPlanId}`; the server reloads the seed and **recomputes** the applied state + outcome via the solver — so no graph checkpoint needs to persist and no DB is required.
- **Trust rule.** The solver recomputes all numbers server-side; the LLM narrative is passed through for display only.
- **Reset** reloads the seed. Nothing is shared between users or requests.

---

## 7. API / Interface Contracts

| Endpoint | In | Out | Notes |
|---|---|---|---|
| `GET /api/health` | — | `{ok, llm_configured}` | existing. |
| `GET /api/state` | — | initial twin state (facts) | from seed. |
| `POST /api/run/stream` | `{presetId}` | **SSE stream** of node events: `{node, role, evidenceUsed[], output, derivedFacts, plans?, verdict?, status}`, terminated by a `done` event carrying the verified plans | validate `presetId`; runs the LangGraph graph; **one model call per node**; budget-bounded; solver supplies all numbers. |
| `POST /api/execute` | `{presetId, approvedPlanId}` | `{twin, applied:true}` | **requires** a plan id produced for this preset/run (FR-EXEC-001); solver applies. |
| `POST /api/outcome` | `{presetId, approvedPlanId}` | `{match, expected, actual, deltas[]}` | solver re-check. |
| `POST /api/reset` | — | initial state | client may also reset locally. |
| `GET /api/integrations` (v0.3) | — | connector manifests `[{id, category, tier, mode:"simulated", capabilities, auth{mode,scopes,rateLimit}, endpoints[], …}]` | simulated only. |
| `GET /api/integrations/{id}/sample` (v0.3) | — | one native-looking payload | powers the payload drawer. |
| `/mock/*` (v0.3) | per connector | fabricated records | OpenAPI tag "Simulated connectors"; same handlers nodes call in-process. |

**v0.3 additive contract fields** (full shapes in `docs/contracts.md`): SSE `integration_call {…, requestId}`; `evidenceUsed[].source`; preset `source` (signed-webhook demo); `done.plannedActions[]` (dry run) and `done.audit[]`; `/api/execute` → `actions[]` (artifacts + idempotency keys) and `audit[]`; `/api/outcome` → `reread[]`. All optional for older clients.

**Validation & errors.** Pydantic on all bodies; error shape `{error, code}` with safe generic messages (NFR-SEC-002). **Streaming:** SSE (`text/event-stream`); on a node failure the stream emits a `failed` event and closes — no fabricated content (FR-ORCH-005). **Idempotency:** a run on the same preset/seed is deterministic in its derived facts; narrative may vary (model), numbers do not. **Versioning:** single internal API; not versioned.

---

## 8. Security Boundaries

- **Secret handling (FR-SEC-001, NFR-SEC-001).** `LLM_BASE_URL/API_KEY/MODEL` (legacy `LITELLM_*` accepted) read from env server-side via `config.py`; passed to `ChatOpenAI(base_url, api_key, model)`; `.env.local` gitignored; never sent to the browser/logged/committed. Only `/api/health` exposes the boolean `llm_configured`.
- **Trust boundaries.** Browser bodies and model output are untrusted; validate `presetId`/`approvedPlanId`; model text is data, never executed, parsed defensively.
- **Authorization.** None by design (single public demo). The one guarded action — `/api/execute` — is gated on an in-run `approvedPlanId`, not identity.
- **Least privilege / data.** No DB, no PII, fabricated data only; one outbound destination (the LiteLLM gateway).
- **Connector boundary (v0.3).** Connectors are in-process and simulated: no outbound network, no real credentials, no persistence (AT-INT-sec-01). Manifests show least-privilege scopes (read-only until approval; write scopes only exercised after `/api/execute` validates `approvedPlanId`). Inbound "webhooks" carry a demo HMAC verified server-side; unverifiable payloads are rejected with `{error, code}`. Writes carry idempotency keys and are audited.
- **Abuse/budget (NFR-OPS-001).** Node budget caps model calls per run; see §9.

---

## 9. Failure Behavior

| Failure | Handling |
|---|---|
| Model (node) timeout/5xx | One bounded retry in `llm.py`, then the node emits `status:"failed"`; the SSE stream sends a `failed` event and ends that path; **no fabricated output** (FR-ORCH-005). Provider error logged server-side without secrets. |
| Not configured | `/api/run/stream` returns 503 with the "configure LiteLLM" guidance. |
| Run near 5-min cap | Run is bounded (node budget) and **streamed** (progress reaches the UI as it happens); **parallel specialist nodes** cut wall-time. New risk: streaming behavior on Vercel (AR5). |
| Budget exhausted | Graph halts with a clear `budget` event (NFR-OPS-001). |
| Verifier rejects | Conditional edge routes back to `planner_node` **once**; a revised plan is emitted (FR-VER-002, FR-ORCH-004). |
| No feasible plan | Plans still emitted, each naming violated constraints (FR-PLAN-004). |
| Execute without approval | `/api/execute` refuses without a valid in-run `approvedPlanId` (FR-EXEC-001). |
| Reset mid-run | Client discards the stream/working state; no external effect. |
| Connector call fails (v0.3) | Emit `integration_call` with a failed status; the node proceeds only with data it actually has (or fails honestly); optional outage simulation labels fallback data "Last-known snapshot". **No fabricated data** (FR-INT-006). |
| Invalid webhook signature (v0.3) | Reject with `{error, code}`; no run starts. |

Rollback/compensation: n/a — execution mutates only the client's working twin, restored by reset.

---

## 10. Deployment & Configuration

- **Platform:** Vercel Hobby, Python/FastAPI preset; auto-deploy on push to `main`.
- **Config:** env `LLM_BASE_URL/API_KEY/MODEL` (any OpenAI-compatible gateway; the LiteLLM gateway for submission; legacy `LITELLM_*` accepted); optional `DEMO_PASSCODE`, `MAX_CALLS_PER_RUN`.
- **Build:** pinned `requirements.txt`; `vercel.json` added only once the first deploy shows what routing/streaming config is needed (AR4/AR5). **Verify the langchain bundle fits Vercel's function size limit (AR6).**
- **Rollback/recovery:** redeploy a prior build; stateless, nothing to restore.

---

## 11. Observability & Operations

- **Structured logs** per run/node: `runId, node, role, duration_ms, provider_status, call_count, budget_remaining`. Never log the key, prompts, or full payloads (NFR-OPS-002).
- **Health:** `/api/health` → `{ok, llm_configured}`.
- **Support owner:** the participant.

---

## 12. Test Approach

| Layer | What | Real vs. mock |
|---|---|---|
| **Unit** | `twin.solver` — scheduling, completion, cost, eligibility, candidate plans, outcome. Deterministic, highest value. | Real, no model. |
| **Integration** | The LangGraph graph: node execution order, the **conditional verifier→planner edge** (rejection → revised plan), budget cap, honest node failure, deterministic derived facts. `/api/execute` approval gate + outcome + reset. | **A fake chat model** (LangChain `GenericFakeChatModel`/stub) injected via `llm.py` — asserts node invocation and routing; no paid calls. |
| **E2E / smoke** | Happy path of Flow A through the streamed run + approval + outcome. | Fake model, or one cheap real call in a smoke run. |
| **Security** | Key/`sk-` scan; real-data review. | Static scan + manual. |

---

## 13. Decisions & Risks

### Architecture decisions (ADRs)

- **ADR-001 — Deterministic solver owns all numbers; nodes reason/explain only.** Unchanged. Graph nodes call `twin.solver` for every figure (FR-PLAN-003).
- **ADR-002 (revised v0.2) — LangGraph graph, run streamed in one request to the approval boundary; execution separate.** The investigation→plan→verify graph runs server-side and streams per-node SSE events (visible trail, FR-ORCH-003). The human-approval gate is the boundary between the streamed run and a separate `/api/execute` request, so no cross-request graph state is needed and Vercel statelessness + no-DB still hold (NFR-REL-001). The 5-min ceiling is managed by a bounded node budget, streaming, and parallel specialist nodes (NFR-PERF-001). Prior v0.1 design (client-driven one-call-per-request loop) is superseded.
- **ADR-003 (reversed v0.2) — Use LangGraph for orchestration.** Owner decision. LangGraph gives explicit nodes, handoffs, a conditional edge for the verifier revision, and parallel fan-out — a stronger, more legible multi-agent artifact than a hand-rolled registry, and is allowed by the hackathon guide. Accepted costs: a heavier dependency (AR6) and a single streamed run to manage (AR5).
- **ADR-004 — No database; in-session working state only.** Unchanged.
- **ADR-005 (new v0.3) — Simulated enterprise connectors behind a Connector + manifest interface.** To show how the twin plugs into systems companies already run, `integrations/` provides read adapters (views over the seed) and ActionBuilders (pure functions: solver output + seed facts → artifact) with per-system manifests, demo-HMAC inbound events, idempotency keys and an audit trail. Calls are in-process (no outbound network, AT-EXEC-004 / AT-INT-sec-01 still hold); the same handlers are mounted at `/mock/*` for inspection. Numbers still come only from the solver (ADR-001); artifacts are built **without model calls**. Swapping a simulated adapter for a real vendor adapter is a configuration + adapter change behind the same interface. Consequences: a larger contract surface (frozen in `contracts.md`), P2 schedule risk (cut lines in BUILD_PLAN §6), and an honesty obligation (always labeled Simulated).

### Agent roster (6 core nodes)
Graph nodes for the primary scenario: **Impact → (HR ∥ Finance ∥ Sales) → Planner → Verifier (→ Planner once) → [END]**, then a separate **Execution** step (solver, post-approval). The "Orchestrator" is the graph itself. Observer/Sales-vs-merge and parallel-vs-sequential specialists are tuning choices for TASK-011/013; default is parallel specialist fan-out to cut latency.

### Open items

| ID | Item | Where resolved |
|---|---|---|
| AR1 | Run latency acceptable? | After TASK-010; tune via parallel nodes. |
| AR2 | Passcode/throttle for the public URL. | Phases (P2), PRD OQ4. |
| AR4 | Vercel `/api` routing with the FastAPI preset. | First deploy (TASK-003). |
| **AR5** | **SSE streaming behavior on Vercel Python functions.** | First deploy + TASK-010. |
| **AR6** | **langchain/langgraph bundle vs Vercel function size limit.** | First deploy (TASK-003). |
| AR7 | `/mock/*` path prefix deploys alongside `/api/*` on Vercel. | First push after TASK-024. |
| AR8 | Connector breadth vs schedule; artifact-shape contract growth. | BUILD_PLAN §6 cut lines; shapes frozen in `contracts.md`. |

### Consistency with PRD
Implements PRD v0.2 (Domain INT, P2) via ADR-005; LangGraph remains a mechanism. Every existing FR/NFR keeps its meaning and ID; the solver still guarantees FR-PLAN-003; failure/budget behavior still realizes NFR-REL/OPS/PERF.
