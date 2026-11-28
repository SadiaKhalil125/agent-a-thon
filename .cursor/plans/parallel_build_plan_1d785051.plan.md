---
name: Parallel build plan
overview: "Split CompanyTwin AI into two fully independent tracks (Person A: engine = twin, solver, LangGraph, API, simulated connectors; Person B: experience = UI/UX incl. Connected Systems hub) joined only by a frozen API contract with mock fixtures, so both can work in parallel with zero file overlap. Includes a production-style simulated integrations layer (HRIS, tracker, ERP/accounting, CRM, calendar as evidence sources; messaging, email, docs, sheets, scheduling, e-sign as an Action Center; connector manifests, signed webhooks, idempotency keys, audit trail, dry-run preview) and ready-to-paste agent prompts for each person."
todos:
  - id: c0-contract
    content: "C0 (together, 20 min): write and freeze docs/contracts.md (incl. integrations section), confirm file ownership, align with docs/BUILD_PLAN.md, agree feat/TASK-NNN-brief branch naming"
    status: pending
  - id: c0-docs-change
    content: "C0 (A authors, owner approves): change-control commit to docs: PRD v0.2 (FR-INT-001..006, AT-INT, narrow section 4.3 exclusion to REAL integrations), architecture v0.3 (integrations/ module, Connector + manifest + ActionBuilder), rules (dependency direction, no outbound network), phases (TASK-024..028)"
    status: pending
  - id: a-int1-connectors
    content: "A-INT1: TASK-024 integrations/ package: Connector base + manifest (auth mode, scopes, rate limit) + registry; tier-1 read adapters (hris, tracker, erp, crm, calendar) as pure views over seed; /mock/* dummy endpoints with OpenAPI tag; GET /api/integrations (+/sample); unit tests"
    status: pending
  - id: a-int2-readthrough
    content: "A-INT2: TASK-025 nodes read evidence through connectors and emit integration_call events (requestId); presets from different systems carry source with demo HMAC signature (event inbox); evidenceUsed[].source; audit[] entries"
    status: pending
  - id: a-int3-writeback
    content: "A-INT3: TASK-026 Action Center: ActionBuilder functions (tracker update, ERP PO, CRM note, messaging post, email draft, docs recovery plan, sheets export, scheduling invite, e-sign SOW, calendar block) from solver output; dry-run plannedActions[] in done; actions[] with idempotency keys in /api/execute; reread[] in outcome; tests assert no outbound network, no persistence, idempotent replay"
    status: pending
  - id: a-int4-stretch
    content: "A-INT4 (stretch): TASK-028 vendor-management read, spreadsheet read, meet transcript, X-Simulate-Outage degradation path; only if ahead at C4"
    status: pending
  - id: b-int1-hub
    content: "B-INT1: TASK-027a Connected Systems hub (tiles by tier, Simulated badge, auth/scopes/rate-limit chips, payload drawer, endpoint list) + event inbox: preset cards with signed-webhook payload on the disruption step"
    status: pending
  - id: b-int2-trail-chips
    content: "B-INT2: TASK-027b integration-call chips inside the agent trail (system, method, path, status, ms) + source links on evidence chips"
    status: pending
  - id: b-int3-writeback-ux
    content: "B-INT3: TASK-027c Action Center: dry-run preview grid before approval, live artifact cards after execute (message, email draft, document, spreadsheet, calendar invite rich previews; others generic), idempotency chips, audit log drawer, re-read confirmation in outcome panel"
    status: pending
  - id: a1-seed-model
    content: "A1: TASK-004/005 seed northstar.json, loader/validation, twin model"
    status: pending
  - id: a2-solver
    content: "A2: TASK-006/007 deterministic solver (+schedule, apply, outcome), publish golden fixtures to tests/fixtures"
    status: pending
  - id: a3-state-api
    content: "A3: GET /api/state + presets endpoint per contract"
    status: pending
  - id: a4-llm-factory
    content: "A4: TASK-008 agents/llm.py ChatOpenAI factory + fake chat model"
    status: pending
  - id: a5-graph-slice
    content: "A5: TASK-009/010 LangGraph state/budget/graph + Impact node + /api/run/stream SSE; prove Vercel SSE and bundle size"
    status: pending
  - id: a6-full-graph
    content: "A6: TASK-011/012/013 parallel HR/Finance, Planner (>=2 plans), Verifier reject->revise once"
    status: pending
  - id: a7-execute
    content: "A7: TASK-014 execute/outcome/reset with server-side approval gate"
    status: pending
  - id: a8-hardening
    content: "A8: TASK-019/020/021 budget cap, honest failure, deterministic re-run, key and data scan"
    status: pending
  - id: a9-cleanup
    content: "A9: remove /api/chat after UI migrated, update memory.md backend section with real evidence"
    status: pending
  - id: b1-design-system
    content: "B1: TASK-002 rebrand + extended tokens, light/dark, reusable components (StepCard, StatusBadge, FactTag, PlanCard, Alert, Skeleton)"
    status: pending
  - id: b2-client-mock-shell
    content: "B2: api-client.js live/mock switch, static/mock fixtures, mock SSE player with 4 variants, sectioned shell + progress rail"
    status: pending
  - id: b3-company-state
    content: "B3: TASK-015 company state, animated dependency chain, people/budget panels, skeletons"
    status: pending
  - id: b4-agent-trail
    content: "B4: TASK-016 live agent trail (parallel HR/Finance, failed state + Retry, evidence chips, FactTags)"
    status: pending
  - id: b5-plans-gantt
    content: "B5: TASK-017 plan comparison + working-day Gantt + verdict ribbon + rejected->revised link"
    status: pending
  - id: b6-approval-outcome
    content: "B6: TASK-018 approval confirm, before/after Gantt morph, outcome banner/deltas, reset/re-run"
    status: pending
  - id: b7-polish
    content: "B7: TASK-022 keyboard/a11y/responsive/contrast/motion/microcopy/perf pass"
    status: pending
  - id: b8-integration
    content: "B8: flip to live API, delete chat.js and chat form, incognito walkthrough, update memory.md frontend section"
    status: pending
  - id: c5-release
    content: "C5 (together, Mon AM): full incognito E2E on prod URL, sk- scan, <=600 char summary, submit by ~12:00 PKT"
    status: pending
isProject: false
---

# Parallel Build Plan — CompanyTwin AI (two people, two agents)

Current state (verified from the pulled repo): TASK-001 scaffold is done and every module under `twin/`, `agents/`, `orchestration/`, `api/` is a stub. Vercel is already deployed. The UI is still the chat starter in [templates/index.html](templates/index.html) and [static/js/chat.js](static/js/chat.js). Deadline per [HACKATHON.md](HACKATHON.md): Mon Nov 30, 2:00 PM PKT (R7 says confirm Nov 29 vs 30). Plan targets the original Day-2 release (Sun night), with Monday morning kept as buffer only.

## 0. Alignment with [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) (the original plan stays authoritative)

This plan does not replace the original. It runs the same blocks in parallel across two people. Where the two differ, BUILD_PLAN.md wins.

**Kept exactly as in BUILD_PLAN.md**
- Same six agents as LangGraph nodes: Impact Investigator, Planner, Verifier, Finance, HR/Resource, Execution. Orchestrator is the `StateGraph` itself (no model call). Observer and Sales stay out of the core set and are stretch nodes only.
- Same ticket order and numbering (TASK-004 to TASK-021, 023), same file list, same "numbers only from the solver" rule, same honest-failure and budget rules, same Fact / Calculated / Estimate tags.
- Same "what makes it win" demo spine: departments visibly connected, Verifier rejects and Planner revises, solver-backed numbers, closed approval loop, repeatable with no presenter.
- Foundation is already done: TASK-001 scaffold exists and Vercel is deployed (TASK-003), so Block 1 is complete.

**Build priority = "hero trio first".** If time runs short, these three must be finished before anything else: Impact, Planner, Verifier. So A6 order is Planner, then Verifier (reject then revise), then Finance, then HR. Execution is solver-backed apply plus outcome verification; Observer and Sales are only added if ahead.

**Day-1 milestone is preserved.** End of Day 1 (Sat night) is a live Vercel URL where triggering the event shows the Impact agent doing real, solver-backed cross-department tracing, streamed. The simulated-integrations work is deliberately scheduled after this milestone so it cannot delay it.

**What is new compared with BUILD_PLAN.md (needs your approval, kept low-risk)**
- The two-person split, file ownership and the frozen `docs/contracts.md`, so nothing blocks on anyone.
- The UI is built in parallel from Day 1 against mock data (BUILD_PLAN put UI in Day 2 Block 6), which frees Day 2 for integration, polish and hardening.
- Simulated enterprise integrations (section 3a): P2, after the Day-1 milestone, with a cut line.
- At least 3 presets with different inputs (for example developer out days 1 to 5, days 1 to 3, backup also unavailable) so a judge can change an input and see a different result (BUILD_PLAN demo spine item 5). Custom parameters stay stretch (TASK-S1).

**Naming and process alignment**
- Branches follow rules.md: `feat/TASK-NNN-brief` (for example `feat/TASK-006-solver`). The two people never work the same TASK, so there is no overlap. Commit messages include `TASK-NNN`.
- The SSE client file keeps its architecture name `static/js/run.js`; `static/js/api-client.js` is the thin live/mock switch that `run.js` uses.
- Backend test files follow architecture: `tests/test_solver.py`, `tests/test_graph.py`, `tests/test_security.py` (BUILD_PLAN's verification section mentions `test_run_steps.py`, which is the older name for `test_graph.py`).
- TASK-022 (accessibility and responsive) is "stretch if ahead" in BUILD_PLAN; here B7 does it as part of polish because UX quality is a stated priority.

## 1. How the split works

- **Person A — Engine (Backend + Agents + simulated connectors).** Owns the numbers, the LangGraph run, the API and the dummy enterprise endpoints. Needs no UI to be productive: pytest plus `curl.exe -N` for SSE.
- **Person B — Experience (Frontend + UX).** Owns everything the evaluator sees, including the Connected Systems hub. Needs no backend to be productive: builds against fixtures and a mock API layer that mimics the contract exactly.
- **The only coupling is `docs/contracts.md`** (the frozen API contract, section 3). Neither person edits the other's files. Integration is a one-line switch from mock to live.

```mermaid
flowchart LR
  subgraph personA [Person A Engine]
    seedModel[seed + model] --> solver[solver]
    solver --> graphRun[LangGraph nodes]
    graphRun --> apiLayer[api routes SSE]
  end
  subgraph personB [Person B Experience]
    designSys[design system] --> screens[screens + animations]
    screens --> apiClient[api-client mock or live]
  end
  contract[contracts.md frozen] --- apiLayer
  contract --- apiClient
  apiLayer -->|"integration swap"| apiClient
```

## 2. File ownership (zero overlap = zero merge conflicts)

**Person A owns (B must not edit):**
- [twin/](twin/), [data/seed/](data/seed/), [agents/](agents/), [orchestration/](orchestration/), [api/](api/), new `integrations/` (simulated connectors) and `api/integrations.py`
- [app.py](app.py) (router mounting incl. `/mock/*`, `/api/chat` removal at the end), [config.py](config.py)
- Planning docs [docs/PRD.md](docs/PRD.md), [docs/architecture.md](docs/architecture.md), [docs/rules.md](docs/rules.md), [docs/phases.md](docs/phases.md): A is the single author of the C0 change-control commit (so there is never a docs conflict); B only edits [docs/design.md](docs/design.md)
- [tests/](tests/) (except `tests/ui/`), [pyproject.toml](pyproject.toml), [requirements.txt](requirements.txt), [requirements-dev.txt](requirements-dev.txt), [.github/](.github/)

**Person B owns (A must not edit):**
- [templates/index.html](templates/index.html), [static/](static/) (css, js incl. `static/js/integrations.js`, new `static/mock/` incl. `integrations.json` and `execute.json`), [branding.py](branding.py)
- [FRONTEND.md](FRONTEND.md), [docs/design.md](docs/design.md), `tests/ui/`

**Shared, rule-governed:**
- `docs/contracts.md`: created together in the first 20 minutes, then frozen. Additive optional fields are allowed with a heads-up message; breaking changes need both people.
- [docs/memory.md](docs/memory.md): each person edits only their own section ("Backend track" / "Frontend track") to avoid conflicts.
- [docs/phases.md](docs/phases.md): status column only, one row at a time, rebase before editing.
- `app.py` placeholder tokens (`{{PAGE_TITLE}}` etc.): B may not add new `{{TOKENS}}`; B hardcodes new copy in the template or reuses existing tokens. This removes the only hidden coupling between the two tracks.

**Git hygiene:** branches `feat/TASK-NNN-brief` per rules.md (A uses backend tickets, B uses UI tickets, never the same one); small PRs; rebase on `main` at least every few hours; `main` auto-deploys, so it must always boot. B's UI ships early because its mock fallback keeps the page working while the backend is unfinished.

## 3. The frozen contract (`docs/contracts.md`, v1)

Both agents code against this. Numbers shown in fixtures are illustrative until A's solver publishes real golden samples at checkpoint C1.

- `GET /api/health` → `{ok, llm_configured}` (exists)
- `GET /api/state` → initial twin: `{company, projects[], tasks[{id,projectId,type,days,dependsOn[]}], people[{id,name,skills[],availability[{startDay,endDay}],assignments[]}], milestones[], commitments[], invoices[], budget, contractor, chain[{id,type,label}], presets[{id,label,description}]}`
- `POST /api/run/stream {presetId}` → SSE. Event names and payloads:
  - `run_started {runId, presetId, event, budget:{max,used}}`
  - `node_started {node, role}` (node ids: `impact`, `hr_resource`, `finance`, `planner`, `verifier`; `hr_resource` and `finance` start together to show parallelism)
  - `node_completed {node, role, status:"done"|"failed"|"rejected"|"revised", evidenceUsed[{ref,label}], output, derivedFacts[{label,value,tag:"fact"|"calculated"|"estimate"}], plans?, verdict?, budget}`
  - `budget {max, used}` and `failed {node, message}` (no fabricated content)
  - `done {plans[], verdict, budget}`
- `Plan` = `{id, name, summary, status:"proposed"|"rejected"|"revised"|"verified", revisesPlanId?, projectCompletion:{A,B}, deadlines[{name,dueDay,met}], incrementalCost, budgetFit, invoiceEligible, violatedConstraints[], schedule[{taskId,personId,startDay,endDay}]}` (`schedule` powers the Gantt view)
- `POST /api/execute {presetId, approvedPlanId}` → `{applied:true, twin}`; refuses without a valid plan id (error shape `{error, code}`)
- `POST /api/outcome {presetId, approvedPlanId}` → `{match, expected, actual, deltas[]}`
- `POST /api/reset` → initial state
- **Integrations (additive, all optional for older clients):**
  - `GET /api/integrations` → connector manifest list `[{id, category, tier:1|2|3, label, mode:"simulated", status:"connected", capabilities:["read","write","webhook","artifact"], auth:{mode:"oauth2"|"api_key"|"webhook_hmac", scopes[], rateLimit}, lastSync, endpoints[{method,path,direction:"read"|"write"}], recordCount}]`. Ids: `hris`, `tracker`, `erp`, `crm`, `calendar` (tier 1); `messaging`, `email`, `docs`, `sheets`, `scheduling`, `esign` (tier 2 action sinks); `vendor`, `meet` (tier 3 stretch).
  - `GET /api/integrations/{id}/sample` → one representative payload in that system's native-looking schema (powers the payload drawer)
  - SSE `integration_call {node, system, method, path, direction, status, durationMs, requestId, summary}` emitted whenever a node reads through a connector (a deterministic tool call, not a model call, so it does not consume model budget)
  - `evidenceUsed[].source = {system, path, recordId}` (e.g. tracker `NS-142`)
  - preset `source = {system, eventType, payload, signature:"verified (demo)"}`; presets arrive from different systems (HRIS `leave.approved`, calendar `out_of_office.created`, tracker `assignee.unavailable`) so the "event inbox" shows breadth
  - `done` and `POST /api/execute` gain `audit[{ts, requestId, actor:"agent:<node>"|"human:approver", system, action, planId?, result}]`
  - `POST /api/execute` response gains `actions[{id, system, kind, status:"simulated_ok"|"simulated_failed", idempotencyKey, summary, artifact}]` where `kind` and `artifact` are: `message{channel,text}`, `email_draft{to,subject,body}`, `document{title,sections[]}`, `spreadsheet{sheet,columns[],rows[][]}`, `calendar_event{title,start,end,attendees[],joinLink}`, `esign{docTitle,signers[],status}`, `ticket_update{key,changes[]}`, `purchase_order{id,vendor,amount}`, `crm_note{accountId,text}`, `calendar_block{person,startDay,endDay}`
  - `POST /api/run/stream` response also includes a **dry-run** `plannedActions[]` (same shape as `actions[]`, `status:"planned"`) inside `done`, so the UI can preview the Action Center before approval
  - `POST /api/outcome` gains `reread[{system, path, match}]`
  - Dummy endpoints themselves live under `/mock/*` (see section 3a)

Mock rule for B: `static/js/api-client.js` has `MODE = live | mock`. Default is live with automatic fallback to `static/mock/*` when an endpoint returns 404/501, plus a small "Demo data" badge. A mock SSE player replays `static/mock/run-stream.json` with realistic delays and includes failure, budget-exhausted and no-feasible-plan variants.

## 3a. Simulated enterprise integrations (new)

Goal: show that CompanyTwin plugs into the systems a company already runs, using dummy endpoints, without pretending they are real. This directly serves the rubric's Business value, Completeness and Creativity criteria.

**Scope change to approve (you are the owner):** [docs/PRD.md](docs/PRD.md) §4.3 currently excludes "live integrations, webhooks". The change-control commit at C0 narrows that to **real** integrations (still excluded) and adds **simulated connectors** as in scope: FR-INT-001 simulated enterprise systems with dummy endpoints, a connector manifest and visible OpenAPI; FR-INT-002 agents cite the source system through a visible integration call; FR-INT-003 inbound events arrive from different systems as signed webhooks (event inbox); FR-INT-004 Action Center: after human approval the plan fans out into simulated actions across systems, with a dry-run preview before approval and an outcome re-read after; FR-INT-005 every write carries an idempotency key and every call/action is in an audit trail; FR-INT-006 every connector labeled "Simulated" in the UI. New tickets TASK-024 to TASK-027 (core) and TASK-028 (stretch). Priority P2 but scheduled in the main path because it is the "practical for production" story; cut lines below.

**Why these systems:** a project-recovery decision touches who is free (HR, calendar), what work is blocked (tracker), what it costs and bills (ERP/accounting, spreadsheets), who the customer is and what was promised (CRM), who can be hired (vendor management), and then everyone has to be told and scheduled (messaging, email, docs, scheduling, e-signature). That is the real operating surface of a company.

**Tier 1 — read connectors that feed evidence** (category names only, no brand logos, so nothing implies a real vendor integration):
- **`hris` HR software:** `GET /mock/hris/employees`, `GET /mock/hris/leave-requests`, inbound `POST /mock/hris/webhooks/leave-approved` (primary disruption trigger).
- **`tracker` Jira-style:** `GET /mock/tracker/issues`, `GET /mock/tracker/issues/{key}` (e.g. `NS-142`), `GET /mock/tracker/sprints/current`.
- **`erp` ERP / accounting (NetSuite- or QuickBooks-style):** `GET /mock/erp/invoices`, `GET /mock/erp/budgets/recovery`, `GET /mock/erp/purchase-orders`.
- **`crm` CRM:** `GET /mock/crm/accounts/{id}`, `GET /mock/crm/commitments` (with SLA and penalty clause references).
- **`calendar` Calendar:** `GET /mock/calendar/freebusy?person=`, `GET /mock/calendar/events` (out-of-office events are an alternate disruption trigger).

**Tier 2 — action sinks (artifacts the Action Center produces after approval):**
- **`tracker`:** reassign issue and move due date (`ticket_update`).
- **`erp`:** contractor purchase order (`purchase_order`) and invoice milestone note.
- **`crm`:** customer notification note (`crm_note`).
- **`messaging` Slack/Teams-style:** post to a war-room channel (`message`).
- **`email` Gmail/Outlook-style:** customer apology/status draft (`email_draft`).
- **`docs` Docs-style:** auto-generated recovery plan and decision record (`document`).
- **`sheets` Sheets-style:** updated capacity and plan-comparison sheet export (`spreadsheet`).
- **`scheduling` Calendly-style:** book a steering call with the customer and stakeholders (`calendar_event`).
- **`esign` e-signature:** contractor statement-of-work envelope (`esign`).
- **`hris`/`calendar`:** coverage block for the backup developer (`calendar_block`).

**Tier 3 — stretch (only if ahead):** `vendor` (staffing/vendor management: contractor availability, rate card, quote, which backs the $1,500 option), a spreadsheet **read** (capacity sheet as an input), `meet` (Meet-style transcript as a context source only; PRD excludes transcription as a product), payments/billing, time tracking, support ticketing, and an **outage simulation** (header `X-Simulate-Outage: <system>`; the call returns 503 and the node proceeds from the seed snapshot labeled "Last-known snapshot", no fabricated content).

**Production-readiness layer (shown, all simulated):**
- A connector **manifest** per system: auth mode (OAuth2, API key, signed webhook), least-privilege scopes (read-only until approved, write scopes only exercised after approval), rate limit, capabilities. Visible in the hub drawer.
- **Idempotency keys** on every write and a `requestId` on every call, so retries are safe and calls are traceable.
- **Audit trail** of every agent read, human approval and action (`audit[]`), with an "Audit log" drawer in the UI.
- **Dry run before approval:** the same actions shown as `planned`, which makes the approval gate concrete ("here is exactly what will be sent where").
- **Signed inbound webhooks** (demo HMAC verified server-side, shown as "signature verified (demo)") and an **event inbox** where presets come from different systems.
- **Honest degradation:** a failed call shows a failed integration chip, never fabricated data.
- A `Connector` interface plus manifest means swapping a simulated adapter for a real vendor adapter is a configuration and adapter change; this is the extension story for the pitch.

**How it fits the architecture without breaking any rule:**
- `integrations/` is a pure adapter layer over the seed. Each seed entity gets `source:{system, externalId}` so records look like they came from the tracker, the ERP, the CRM, the HRIS or the calendar, each in its own native-looking JSON schema.
- Calls are **in-process** (no outbound network), so the existing guarantee "no outbound call except the LLM gateway" (AT-EXEC-004) still holds. The same handlers are also mounted over HTTP at `/mock/*` with an OpenAPI tag "Simulated connectors", so judges can open `/docs` and see the endpoints.
- **Numbers still come only from `twin/solver.py`.** Connectors supply records and evidence, never calculations. Nodes call connectors as deterministic tools and emit `integration_call` events.
- The Action Center is simulated and stateless: `/api/execute` returns `actions[]` with generated artifacts (message, email draft, document, spreadsheet, calendar event, e-sign envelope, ticket update, purchase order, CRM note); nothing persists and nothing leaves the process. Artifacts are built deterministically from solver output and seed facts by small pure functions (10 to 20 lines each); no extra model calls. Outcome verification re-reads the systems and reports `reread[]`.
- Cheap by design: read connectors are thin views over the seed; all Tier 2 sinks share one generic `ActionBuilder` interface, so adding a system is a manifest entry plus one small function.
- Extension point for the pitch: a `Connector` interface with `read()`, `write()` and a manifest; documented in architecture v0.3.
- Directory: `integrations/{base,manifest,registry,hris,tracker,erp,crm,calendar}.py`, `integrations/actions/{messaging,email,docs,sheets,scheduling,esign,tracker,erp,crm}.py`, `api/integrations.py`, `tests/test_integrations.py`.

**UI for B (signature moments):**
- **Connected Systems hub** under the company state: tiles grouped by tier, a persistent "Simulated connectors, demo data" badge, and per tile the auth mode, scopes, rate limit and last sync; a drawer with endpoint list and a "View payload" JSON viewer with copy.
- **Event inbox:** the disruption step shows presets as cards, each with its source system glyph and incoming signed-webhook payload ("signature verified (demo)"); the primary button reads "Receive event". Different presets arrive from HR, calendar or tracker.
- **Integration chips in the agent trail:** each read shows system glyph, method, path, status, milliseconds (for example Tracker GET issues NS-142, 200, 84 ms) and a request id; evidence chips link to their source record.
- **Action Center (signature moment):** before approval, a greyed "Dry run: will be sent on approval" grid; after approval, each card turns live with a check, an idempotency key chip and a Simulated badge. Artifact cards render as real-looking previews: a chat message, an email draft, a recovery-plan document, a spreadsheet table, a calendar invite with join link, an e-sign envelope, a ticket diff, a purchase order. Build five rich previews first (message, email, document, spreadsheet, calendar invite); the rest use a generic key-value card.
- **Audit log drawer:** time-ordered list of every agent read, the human approval and each action, with request ids; plus "Re-read from systems" confirmation in the outcome panel.

**Cut lines if behind at C3 (drop in this order):** esign, calendar_block, Tier 3, outage simulation, then scheduling. Never drop: HRIS-sourced event inbox, tracker read and update, ERP read and purchase order, CRM read and note, messaging post, email draft, docs and sheets artifacts, the hub, trail chips, dry-run preview, audit log.

## 4. Person A — Engine track (order matters)

1. **A1** TASK-004/005: `data/seed/northstar.json` (PRD §10 scenario: dev out days 1–5, backup busy on Project B days 2–3, contractor $1,500, budget $2,000, invoice $8,000), loader + validation in `twin/seed.py`, entities in `twin/model.py`; AT-TWIN-001-01.
2. **A2** TASK-006/007: `twin/solver.py` — impact chain, completion days, deadline impact, cost, eligibility, 3 candidate plans (wait / reassign backup / contractor) with `schedule`, apply plan, outcome check; pure functions, heavy unit tests. Publish golden payloads to `tests/fixtures/` and message B (checkpoint C1).
3. **A3** `GET /api/state` + presets in `api/state.py` (unblocks B's live mode early). Cheap, ship first.
   - **A-INT1** TASK-024 runs after the Day-1 milestone (after A5, Sun morning), not before it, so it cannot delay the live Impact slice. About 2 h: `Connector` base + manifest + registry, five tier-1 read adapters (views over the seed), `/mock/*` endpoints, `GET /api/integrations` and `/sample`, unit tests. B's hub uses mock data until then.
4. **A4** TASK-008: `agents/llm.py` `ChatOpenAI` factory (uses `config.get_llm_settings()`), one bounded retry, fake chat model for tests.
5. **A5** TASK-009/010: `orchestration/state.py`, `budget.py`, `graph.py`, Impact node, `POST /api/run/stream` SSE emitting exactly the contract events. Prove SSE works on Vercel (AR5) and bundle size (AR6).
6. **A6** TASK-012/013 then 011 (hero trio first): Planner (≥2 plans from solver candidates), then Verifier with the single reject→revise conditional edge using a seeded rejectable candidate (backup double-booking Project B), then Finance and HR nodes running in parallel. The graph must be demo-complete after Planner + Verifier even before the specialists land.
   - **A-INT2** TASK-025 alongside A6: nodes fetch the records they cite through connectors and emit `integration_call` events with `requestId`; presets from HRIS, calendar and tracker carry a signed-webhook `source` (demo HMAC, verified server-side); `evidenceUsed[].source` and `audit[]` populated.
7. **A7** TASK-014: `/api/execute`, `/api/outcome`, `/api/reset` with the server-side approval gate.
   - **A-INT3** TASK-026 alongside A7 (about 2.5 h): `ActionBuilder` functions per system turn solver output plus seed facts into artifacts; `plannedActions[]` (dry run) in `done`, `actions[]` with idempotency keys in `/api/execute`, `reread[]` in outcome; tests assert no outbound network, no persisted state, and that replaying the same idempotency key returns the same result. Build order inside the ticket: messaging, email, tracker update, ERP PO, CRM note, docs, sheets, scheduling, then e-sign and calendar block.
   - **A-INT4** TASK-028 (stretch, only if ahead at C4): vendor-management read (backs the contractor option), spreadsheet read, meet transcript, `X-Simulate-Outage` degradation.
8. **A8** TASK-019/020/021: budget cap, honest failure and not-configured paths, deterministic re-run, key/`sk-` scan, input-validation negatives.
9. **A9** Integration cleanup: remove `/api/chat` from [app.py](app.py) after B's UI no longer calls it; update [docs/memory.md](docs/memory.md) backend section with real command output.

## 5. Person B — Experience track (order matters)

Design direction (answers "eye catching + extraordinary UX"): keep the approved warm linen / cognac / Poppins identity from [FRONTEND.md](FRONTEND.md) (no purple gradients, no sparkles, no emoji, inline SVG icons only), and layer in the semantic status colors and fact-tag system from [docs/design.md](docs/design.md). Default decision flagged for you both: design.md's blue `--primary` is replaced by the cognac accent; B records this in design.md. Vanilla JS and CSS only, no build step.

1. **B1** TASK-002 + design system: rebrand [branding.py](branding.py) to CompanyTwin / Northstar; extend tokens (status success/warning/danger/info, FactTag, agent-role accents, motion tokens); build reusable components (StepCard, StatusBadge, FactTag, PlanCard, Alert, Skeleton) in [static/css/main.css](static/css/main.css); light and dark.
2. **B2** `api-client.js` with mock/live switch + `static/mock/` fixtures + mock SSE player (this is what makes B fully independent). Replace the chat starter with the sectioned single-page shell and sticky progress rail.
3. **B3** TASK-015 Company State: stat tiles, animated DependencyChain (Integration → QA → Milestone → Customer → Invoice), people/availability chips, budget and contractor panel, skeleton loading; AT-TWIN-002.
   - **B-INT1** TASK-027a: Connected Systems hub (tiles grouped by tier, Simulated badge, auth/scope/rate-limit chips, payload drawer) and the event inbox (preset cards with signed-webhook payloads), driven by `static/mock/integrations.json` until A-INT1 lands.
4. **B4** TASK-016 Agent Trail ("mission control"): live StepCards streaming in, HR and Finance shown side by side while running, pulsing running state, evidence chips, FactTags, failed state with Retry and zero fabricated content, auto-scroll that respects reduced motion; the dependency chain lights up as impact is traced.
   - **B-INT2** TASK-027b: integration-call chips in each StepCard and source links on evidence chips; mock stream includes `integration_call` events.
5. **B5** TASK-017 Plans: side-by-side comparison with a schedule Gantt per plan (working days on the x-axis, people as rows), deadline met/missed chips, cost vs budget bar, verdict ribbon; rejected plan visibly links to its revised successor.
6. **B6** TASK-018 Approval and Outcome: one-tap confirm, "nothing changes until you approve" reinforcement, before/after Gantt morph on execute, match/mismatch banner with per-field deltas, Reset and Re-run.
   - **B-INT3** TASK-027c (about 3 h): Action Center. Dry-run grid beside the approval bar ("will be sent on approval"), live artifact cards after execute (rich previews for message, email draft, document, spreadsheet, calendar invite; generic card for the rest), idempotency chips, audit log drawer, "Re-read from systems" confirmation in the outcome panel. Driven by `static/mock/execute.json` with `plannedActions[]` and `actions[]` until A-INT3 lands.
7. **B7** TASK-022 polish: keyboard-only flow, focus rings, `aria-live` trail, contrast AA in both themes, responsive at 375/768/1280, empty/error/budget/not-configured states, microcopy pass (no AI clichés), performance (no layout shift, CSS-only animation).
8. **B8** Integration: flip default to live, remove [static/js/chat.js](static/js/chat.js) and the chat form, record a clean unassisted walkthrough (AT-UI-001-01) and update the frontend section of [docs/memory.md](docs/memory.md).

## 6. Timeline and sync points (PKT)

- **C0 Sat now (20 min, together):** write and freeze `docs/contracts.md` (including the integrations section); agree ownership table; create branches; you approve the PRD scope change for simulated connectors and A lands the docs change-control commit first.
- **C1 Sat early evening (BUILD_PLAN Block 2):** A has seed + solver green and `/api/state` live (A1 to A3), golden payloads published. B has design system, static shell and mock mode working (B1, B2).
- **C2 Sat night = BUILD_PLAN Day-1 milestone (Block 3):** A has `agents/llm.py`, graph skeleton and budget, and `/api/run/stream` with the real Impact node streaming on the live Vercel URL, proving SSE and bundle size (A4, A5). B has company state and the live trail built on mock, then flipped to live for state plus Impact (B3, start of B4). Integrations are not started yet on purpose.
- **C3 Sun midday (BUILD_PLAN Blocks 4 and 5):** A has Planner, Verifier reject→revise, Finance and HR (A6), then `integrations/` + `/mock/*` + `/api/integrations` (A-INT1) and `integration_call` events (A-INT2). B has trail with integration chips, Connected Systems hub, plans + Gantt (B-INT1, B-INT2, B4, B5). Integrate the full stream. Apply the integrations cut line here if behind.
- **C4 Sun evening (BUILD_PLAN Blocks 5 and 6):** A has execute/outcome/reset with the Action Center (A7, A-INT3); A-INT4 only if ahead. B has approval, outcome, reset and Action Center UX (B6, B-INT3). Loop is closed end to end. Apply the integrations cut line here if behind (esign, calendar_block, Tier 3, then scheduling).
- **C5 Sun night (BUILD_PLAN Block 7):** A hardening: budget cap, honest failure, deterministic re-run, key and data scan (A8). B polish pass (B7). Production deploy and incognito Flow A smoke. **Feature freeze Sun night.**
- **Mon morning (buffer only):** final incognito check, `sk-` scan, submission text (≤600 chars), submit by about 12:00 for a 2-hour buffer before the 2:00 PM deadline. No new features.

Rule: if A is blocked or late, B is unaffected (mock). If B is blocked or late, A is unaffected (curl and pytest). Whoever finishes early takes stretch items: A (S3 constraint-conflict scenario), B (S2 relationship graph view).

## 7. Definition of done for each person

- Real command output reported, never invented: `ruff check . && ruff format --check . && mypy . && pytest -q` (A); same checks plus manual keyboard/responsive/theme checklist from design.md §10 (B).
- Only fabricated data, no key in client or repo, Accept Edits mode, one TASK at a time, contract changes only with both approvals.

## 8. Prompts to give each agent

Open each person's Cursor in Accept Edits mode. Paste the master prompt first, then the phase prompts as you go.

### Person A — master prompt

```
You are the BACKEND/ENGINE agent for CompanyTwin AI (SSI Agent-A-Thon). Work in Accept-Edits mode, one TASK at a time.

READ FIRST, in order: AGENTS.md, docs/BUILD_PLAN.md (the original plan, authoritative: hero trio first, Day-1 milestone = live Impact stream), docs/PRD.md, docs/architecture.md (v0.2, LangGraph), docs/rules.md (v0.2), docs/phases.md, docs/memory.md, docs/contracts.md (frozen API contract, my teammate builds the UI against it).

OWNERSHIP. You may edit ONLY: twin/, data/seed/, agents/, orchestration/, integrations/, api/, app.py, config.py, tests/ (not tests/ui/), pyproject.toml, requirements*.txt, .github/, and docs/PRD.md, docs/architecture.md, docs/rules.md, docs/phases.md (only for the approved change-control commit). You must NOT edit: templates/, static/, branding.py, FRONTEND.md, docs/design.md. My teammate owns those and works in parallel.

INTEGRATIONS (simulated enterprise connectors, owner-approved scope change; plan section 3a). Build integrations/ with a Connector base, a manifest per system (auth mode, least-privilege scopes, rate limit, capabilities) and a registry. Tier 1 read adapters (hris, tracker, erp/accounting, crm, calendar) are pure in-process views over the seed, exposed at /mock/* with an OpenAPI tag "Simulated connectors", plus GET /api/integrations and /api/integrations/{id}/sample. Tier 2 is the Action Center: one small pure ActionBuilder function per system (tracker update, ERP purchase order, CRM note, messaging post, email draft, docs recovery plan, sheets export, Calendly-style scheduling invite, e-sign SOW, calendar block) that turns solver output + seed facts into an artifact, with NO model call. Return a dry-run plannedActions[] in `done` and actions[] (with idempotency keys) from /api/execute, plus audit[] and reread[] in outcome. Presets arrive from different systems as signed webhooks (demo HMAC, verified server-side). Nodes call connectors as deterministic tools and emit integration_call SSE events with a requestId (not model calls). NO outbound network, NO real credentials, NO persistence; every system labeled simulated; replaying an idempotency key returns the same result. Numbers still come only from twin/solver.py. Tier 3 and outage simulation are stretch. Follow docs/contracts.md exactly.

HARD RULES: all numbers come from twin/solver.py (pure, no model calls); agents/nodes never compute numbers; api/* never calls the model directly; one model call per graph node; model only via agents/llm.py (ChatOpenAI -> gateway from config.py); on model failure emit a failed event with NO fabricated content; fabricated data only; never log or expose the key. New dependency, contract change, or security-boundary change => stop and ask me.

CONTRACT: the SSE event names/payloads and Plan shape in docs/contracts.md are frozen. Additive optional fields are fine (tell me); never rename or remove fields.

YOUR ORDER: C0 docs change-control commit (PRD v0.2 FR-INT-001..006 narrowing section 4.3 to REAL integrations, architecture v0.3 integrations/ module with Connector + manifest + ActionBuilder, rules, phases TASK-024..028) -> A1 TASK-004/005 seed+model -> A2 TASK-006/007 solver (publish golden payloads to tests/fixtures/) -> A3 GET /api/state + presets -> A4 TASK-008 llm factory + fake model -> A5 TASK-009/010 graph + /api/run/stream (Impact, SSE; this is the Day-1 milestone, finish it BEFORE any integrations work) -> A-INT1 TASK-024 connector framework + tier-1 read adapters + /mock/* + /api/integrations -> A6 TASK-011/012/013 specialists in parallel, planner (>=2 plans), verifier reject->revise once, with A-INT2 TASK-025 integration_call events, signed-webhook presets, audit -> A7 TASK-014 execute/outcome/reset with approval gate, with A-INT3 TASK-026 Action Center (dry-run + actions + idempotency + re-read) -> A8 TASK-019/020/021 hardening -> A-INT4 TASK-028 only if ahead.

AFTER EACH TASK: run `ruff check . && ruff format --check . && mypy . && pytest -q`, report the real output (say "Not run" if you can't), update only the Backend track section of docs/memory.md, and use branch feat/TASK-NNN-brief (rules.md section 9). Start now with A1 (TASK-004 and TASK-005). Show me the plan for A1 before editing.
```

Phase prompts for A (short):
- "Proceed to A2 TASK-006/007. Build the solver for the PRD §10 scenario with three candidate plans including `schedule[]` per the contract; the reassign-backup plan must be rejectable because it double-books Project B. Then write golden payloads to tests/fixtures/ matching docs/contracts.md."
- "Proceed to A3 and A4: implement GET /api/state with presets exactly per the contract, then agents/llm.py with the fake chat model and the failure path test."
- "Proceed to A-INT1 TASK-024: create integrations/ with the Connector base, per-system manifest (auth mode, scopes, rate limit, capabilities) and registry; add HRIS, tracker, ERP/accounting, CRM and calendar read adapters as pure in-process views over the seed (each seed entity gets source{system, externalId}); mount them at /mock/* with the OpenAPI tag 'Simulated connectors'; add GET /api/integrations and /api/integrations/{id}/sample per the contract; tests proving no outbound network and no persistence."
- "Proceed to A-INT2: make nodes read the records they cite through connectors and emit integration_call events with requestId (not model calls); give presets from HRIS, calendar and tracker a signed-webhook source (demo HMAC verified server-side); populate evidenceUsed[].source and audit[]."
- "Proceed to A-INT3 TASK-026: build the Action Center. One pure ActionBuilder per system in integrations/actions/ (messaging, email, tracker, erp, crm, docs, sheets, scheduling, esign, calendar block) producing the artifact shapes in docs/contracts.md from solver output, no model calls; plannedActions[] in done (dry run), actions[] with idempotency keys in /api/execute, reread[] in /api/outcome; tests for idempotent replay, no network, no persistence. Do esign and calendar block last."
- "Only if ahead (A-INT4 TASK-028): vendor-management read (contractor availability + rate card backing the $1,500 option), spreadsheet read, meet transcript, and the X-Simulate-Outage path that fails the call honestly and labels the snapshot 'Last-known snapshot'."
- "Proceed to A5 TASK-009/010: LangGraph State, node budget, Impact node, POST /api/run/stream emitting contract events. Verify with `curl.exe -N` locally and tell me what to check on Vercel for SSE buffering and bundle size."
- "Proceed to A6: parallel HR and Finance nodes, Planner, Verifier with the single conditional reject->revise edge; add a deterministic test for the rejection and the honest-failure path."
- "Proceed to A7 and A8: execute/outcome/reset with the server-side approval gate, budget cap, key/sk- scan test, input-validation negatives; then remove /api/chat only after I confirm the UI no longer calls it."

### Person B — master prompt

```
You are the FRONTEND/UX agent for CompanyTwin AI (SSI Agent-A-Thon). Work in Accept-Edits mode, one TASK at a time. The UI must be eye-catching, classy and EXTRAORDINARY in UX, never "AI-looking".

READ FIRST, in order: AGENTS.md, docs/BUILD_PLAN.md (the original plan, authoritative: "what makes it win" demo spine), docs/PRD.md (Flow A), docs/design.md, FRONTEND.md, docs/rules.md, docs/phases.md, docs/memory.md, docs/contracts.md (frozen API contract; my teammate builds the backend against it in parallel). The SSE client file is static/js/run.js (per architecture); api-client.js is the live/mock switch it uses.

OWNERSHIP. You may edit ONLY: templates/index.html, static/ (css, js, mock/), branding.py, FRONTEND.md, docs/design.md, tests/ui/. You must NOT edit: twin/, agents/, orchestration/, api/, app.py, config.py, requirements*.txt, pyproject.toml, .github/, tests/ (except tests/ui/). Do not add new {{PLACEHOLDER}} tokens (app.py fills them); reuse existing ones or hardcode copy in the template.

INDEPENDENCE: build against static/mock/ fixtures through static/js/api-client.js with a live/mock switch (default live, auto-fallback to mock on 404/501 with a small "Demo data" badge). Implement a mock SSE player that replays contract-exact events with realistic delays, plus variants: node failed, budget exhausted, verifier rejects then revises, no feasible plan. Never depend on the backend being finished.

DESIGN: keep the approved warm linen / cognac / Poppins identity from FRONTEND.md; extend with semantic status colors, FactTag (Fact / Calculated / Estimate), agent-role accents, motion tokens; light + dark. No purple gradients, no sparkles, no emoji, inline SVG icons only. Vanilla HTML/CSS/JS, no build step. Signature experiences: animated dependency chain that lights up as impact is traced; live agent "mission control" trail with HR and Finance side by side while running; plan comparison with a working-day Gantt per plan; rejected plan visibly linked to its revised successor; before/after Gantt morph on approval; calm match/mismatch outcome. Honest by design: a failed step shows NO fabricated content. Accessibility: keyboard-only completable, aria-live trail, contrast AA, prefers-reduced-motion, responsive at 375/768/1280.

CONTRACT: docs/contracts.md is frozen; if you need a new field, ask me, do not invent it. Fabricated data only; the key never touches the browser.

INTEGRATIONS UI (simulated enterprise systems; plan section 3a). Tier 1 sources: HRIS, tracker, ERP/accounting, CRM, calendar. Tier 2 Action Center sinks: messaging, email, docs, sheets, scheduling, e-sign, plus tracker/ERP/CRM writes. Show them honestly and beautifully. (1) Connected Systems hub: tiles grouped by tier, persistent "Simulated connectors, demo data" badge, per-tile auth mode, scopes, rate limit, last sync, endpoint list, "View payload" drawer with formatted JSON + copy. (2) Event inbox: the disruption presets are cards with a source-system glyph and the incoming signed-webhook payload ("signature verified (demo)"); primary button "Receive event". (3) Integration-call chips in each agent step (system glyph, method, path, status, ms, request id) and source links on evidence chips. (4) Action Center: before approval a greyed dry-run grid "will be sent on approval" from plannedActions[]; after execute each card goes live with a check, idempotency key chip and Simulated badge. Build rich previews for message (chat bubble), email draft, document (recovery plan), spreadsheet (table), calendar invite (with join link); all other kinds use a generic key-value card. (5) Audit log drawer (time-ordered, request ids) and a "Re-read from systems" confirmation in the outcome. Use category names and your own inline SVG glyphs, never real vendor logos, and never imply a real connection. Drive it from static/mock/integrations.json, static/mock/execute.json and the mock stream until the backend is live.

YOUR ORDER: B1 TASK-002 rebrand + design system + components -> B2 api-client + mock + sectioned shell + progress rail -> B3 TASK-015 company state + dependency chain, with B-INT1 Connected Systems hub + event inbox -> B4 TASK-016 agent trail, with B-INT2 integration chips -> B5 TASK-017 plans + Gantt + verdict -> B6 TASK-018 approval/outcome/reset, with B-INT3 Action Center + audit drawer -> B7 TASK-022 polish/a11y/perf -> B8 integration (flip to live, delete chat.js and chat form).

AFTER EACH TASK: verify in a browser at 375/768/1280 in light and dark, report what you actually checked, update only the Frontend track section of docs/memory.md, use branch feat/TASK-NNN-brief (rules.md section 9). Start now with B1. Show me the design-system plan (tokens, components, the decision to replace design.md's blue primary with the cognac accent) before editing.
```

Phase prompts for B (short):
- "Proceed to B2: build api-client.js (live/mock switch + fallback badge), static/mock fixtures matching docs/contracts.md exactly, the mock SSE player with the four variants, and replace the chat starter with the sectioned page shell and sticky progress rail."
- "Proceed to B3 and B4: Company State with animated dependency chain, then the Agent Trail with parallel HR/Finance cards, failed state with Retry, and chain highlighting as impact is traced. Drive everything from the mock stream."
- "Proceed to B-INT1 and B-INT2: build the Connected Systems hub (tiles by tier with auth/scopes/rate-limit chips, Simulated badge, payload drawer), the event inbox of preset cards with signed-webhook payloads on the disruption step, and integration-call chips plus source links inside the agent trail, all from static/mock/integrations.json and the mock stream."
- "Proceed to B-INT3: the Action Center. Dry-run grid beside the approval bar from plannedActions[], live artifact cards after execute from actions[] (rich previews for message, email draft, document, spreadsheet, calendar invite; generic card for esign, ticket update, purchase order, CRM note, calendar block), idempotency chips, audit log drawer, and the 'Re-read from systems' confirmation; keep the Simulated labeling everywhere."
- "Proceed to B5: plan comparison with Gantt from `schedule[]`, deadline chips, cost-vs-budget bar, verdict ribbon, and the rejected-to-revised link animation."
- "Proceed to B6 and B7: approval confirm, before/after Gantt morph, outcome match/mismatch, Reset/Re-run, then the full keyboard/a11y/responsive/microcopy pass against design.md section 10."
- "Proceed to B8 integration: switch default to live against the real API, verify against the deployed URL in incognito, remove chat.js and the chat form, and list any contract mismatches to give to my teammate rather than fixing backend files."

## 9. Risks specific to the parallel split

- Contract drift: mitigated by freezing at C0 and by A publishing real golden payloads at C1 for B to diff against its fixtures.
- Vercel SSE buffering (AR5): A proves it at A5; if it fails, fallback is a buffered run returning the full trail in `done` (contract already supports it because every event is also derivable from `done`). B's mock player must support "buffered" playback so the UI degrades gracefully.
- Design-doc conflict (blue vs cognac): resolved by B1 decision above; change recorded in design.md only.
- Shared `docs/memory.md`: section-per-person rule prevents conflicts.
- Deadline ambiguity (Nov 29 vs 30 2:00 PM PKT, R7): confirm with organizers today; plan above already has a buffer.
- Integrations scope creep: it is P2 and the core Flow A must stay on schedule; mitigated by keeping connectors as thin in-process views over the seed, the section 3a cut line at C3, and B's mock-driven UI so nothing blocks on A.
- Integrations honesty: judges could read "connected" as real; mitigated by the persistent "Simulated connectors, demo data" badge, category names instead of vendor logos, and `mode:"simulated"` in the contract.
- Scope change vs PRD §4.3: needs your explicit approval at C0 and a single-author docs commit by A before code, so traceability (FR-INT to AT-INT to TASK-024..028) stays intact.
- Integration breadth vs time: many systems look expensive but are cheap by design (manifest entry plus one 10 to 20 line pure function each). The real cost is B's artifact previews, so only five get rich renderers; the cut-line order in section 3a protects the schedule.
- Production claims: we show auth modes, scopes, idempotency, audit and signed webhooks as simulated behavior; the pitch must say "designed to plug in via the Connector interface", never "integrated with" a named vendor.
- Contract surface grows (artifact shapes): any change to an `artifact` shape after C0 needs both approvals; B's generic key-value card is the safety net for unknown or late kinds.
- Vercel route clash: `/mock/*` is a new path prefix; verify it deploys alongside `/api/*` on the first push (same AR4 check as the existing routing).