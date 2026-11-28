# API Contract — CompanyTwin AI
Project: CompanyTwin AI (organizational digital twin)
Status: **Frozen v1** (changes need both teammates; see "Change rules")
Version: 1.0
Last updated: 2026-11-28
Based on: docs/PRD.md v0.2, docs/architecture.md v0.3, docs/BUILD_PLAN.md v2 §5

> This is the **only coupling** between Person A (engine) and Person B (experience). A implements it; B builds against it using `static/mock/*` fixtures and the live/mock switch in `static/js/api-client.js`. Numbers in fixtures are illustrative until A's solver publishes golden payloads to `tests/fixtures/` (checkpoint C1); after that, fixtures must be diffed against the real payloads.

## Change rules
- **Frozen:** event names, existing field names and meanings, the `Plan` shape, and every `artifact` shape below.
- **Additive optional fields** are allowed: the author tells the other person in the same hour; consumers must ignore unknown fields.
- **Breaking changes** (rename/remove/retype) need both people's approval and a version bump here (a rules §10 contract change).
- All data is fabricated. No real vendors, names or domains (use `example.com`).

## Conventions
- JSON, UTF-8. Day numbers are working-day integers from the seed (day 1 = first working day).
- Error shape for every non-2xx: `{ "error": "<safe generic message>", "code": "<ValidationError|NotConfigured|BudgetExceeded|UpstreamModelError|InternalError|InvalidSignature>" }`. Never include stack traces or secrets.
- SSE: `text/event-stream`; each event is `event: <name>` + `data: <json>`. On a node failure a `failed` event is sent and no content is fabricated.
- `tag` values: `"fact"` (seed), `"calculated"` (solver), `"estimate"` (labeled uncertainty).

## 1. Core endpoints

### `GET /api/health`
`{ "ok": true, "llm_configured": boolean }` (exists)

### `GET /api/state`
Initial twin (read-only seed view):
```
{ company, projects[], tasks[{id, projectId, type, days, dependsOn[]}],
  people[{id, name, skills[], availability[{startDay, endDay}], assignments[]}],
  milestones[], commitments[], invoices[], budget, contractor,
  chain[{id, type, label}],
  presets[{id, label, description, source?}] }
```
`presets[].source` is defined in §3 (integrations).

### `POST /api/run/stream`  body `{ "presetId": string }`  → SSE
| Event | Payload |
|---|---|
| `run_started` | `{runId, presetId, event, budget:{max, used}}` |
| `node_started` | `{node, role}` — node ids: `impact`, `hr_resource`, `finance`, `planner`, `verifier`; `hr_resource` and `finance` start together (parallel) |
| `integration_call` | see §3 (not a model call; does not consume model budget) |
| `node_completed` | `{node, role, status:"done"\|"failed"\|"rejected"\|"revised", evidenceUsed[{ref, label, source?}], output, derivedFacts[{label, value, tag}], plans?, verdict?, budget}` |
| `budget` | `{max, used}` |
| `failed` | `{node, message}` — no fabricated content |
| `done` | `{plans[], verdict, budget, plannedActions?[], audit?[]}` |

Every event is also derivable from `done` so a buffered (non-streaming) fallback works.

### `Plan`
```
{ id, name, summary, status:"proposed"|"rejected"|"revised"|"verified",
  revisesPlanId?, projectCompletion:{A, B, C?}  /* map keyed by project letter; "C" only in the client-meeting scenario */,
  deadlines[{name, dueDay, met}], incrementalCost, budgetFit, invoiceEligible,
  violatedConstraints[], schedule[{taskId, personId, startDay, endDay}] }
```
`schedule` powers the Gantt view. `verdict` = `{planId, decision:"approved"|"rejected", reason}`.

### `POST /api/execute`  body `{ "presetId", "approvedPlanId" }`
`{ applied: true, twin, actions?[], audit?[] }`. Refuses (error shape) without a plan id valid for this preset/run (FR-EXEC-001). `actions[]` and `audit[]` are defined in §3.

### `POST /api/outcome`  body `{ "presetId", "approvedPlanId" }`
`{ match, expected, actual, deltas[], reread?[] }`

### `POST /api/reset`
Returns the initial state (same shape as `/api/state`).

## 2. Mock rule for Person B
`static/js/api-client.js` has `MODE = live | mock`. Default is live with automatic fallback to `static/mock/*` on 404/501 and a small "Demo data" badge. A mock SSE player replays `static/mock/run-stream.json` with realistic delays and includes variants: node failed, budget exhausted, verifier rejects then revises, no feasible plan, buffered playback.

## 3. Simulated integrations (additive; all optional for older clients; P2)

Everything here is **simulated** (in-process, no outbound network, no credentials, no persistence) and labeled so in the UI.

### `GET /api/integrations`
Connector manifest list:
```
[{ id, category, tier: 1|2|3, label, mode: "simulated", status: "connected",
   capabilities: ["read"|"write"|"webhook"|"artifact"],
   auth: { mode: "oauth2"|"api_key"|"webhook_hmac", scopes[], rateLimit },
   lastSync, endpoints[{method, path, direction:"read"|"write"}], recordCount }]
```
Ids: tier 1 `hris`, `tracker`, `erp`, `crm`, `calendar`; tier 2 (action sinks) `messaging`, `email`, `docs`, `sheets`, `scheduling`, `esign`; tier 3 (stretch) `vendor`, `meet`.

### `GET /api/integrations/{id}/sample`
One representative payload in that system's native-looking schema (powers the payload drawer).

### `/mock/*` dummy endpoints (OpenAPI tag "Simulated connectors")
- `hris`: `GET /mock/hris/employees`, `GET /mock/hris/leave-requests`, `POST /mock/hris/webhooks/leave-approved`
- `tracker`: `GET /mock/tracker/issues`, `GET /mock/tracker/issues/{key}`, `GET /mock/tracker/sprints/current`
- `erp`: `GET /mock/erp/invoices`, `GET /mock/erp/budgets/recovery`, `GET /mock/erp/purchase-orders`
- `crm`: `GET /mock/crm/accounts/{id}`, `GET /mock/crm/commitments`
- `calendar`: `GET /mock/calendar/freebusy?person=`, `GET /mock/calendar/events`
Tier-3 (stretch) endpoints are documented when TASK-028 starts. Optional header `X-Simulate-Outage: <system>` makes that system return 503.

### SSE `integration_call`
`{ node, system, method, path, direction:"read"|"write", status, durationMs, requestId, summary }`

### Evidence source
`evidenceUsed[].source = { system, path, recordId }` (for example tracker `NS-142`).

### Preset source (event inbox)
`presets[].source = { system, eventType, payload, signature: "verified (demo)" }`. At least three presets from at least two systems, for example `hris`/`leave.approved`, `calendar`/`out_of_office.created`, `tracker`/`assignee.unavailable`. The signature is a demo HMAC verified server-side; a tampered payload is rejected with `InvalidSignature`.

### Audit
`audit[] = [{ ts, requestId, actor: "agent:<node>" | "human:approver", system, action, planId?, result }]`, ordered by time, returned in `done` and `/api/execute`.

### Actions (Action Center)
`done.plannedActions[]` (dry run, `status:"planned"`) and `/api/execute` → `actions[]` share one shape:
```
{ id, system, kind, status: "planned"|"simulated_ok"|"simulated_failed",
  idempotencyKey, summary, artifact }
```
Replaying the same `idempotencyKey` returns an identical result. `artifact` by `kind`:

| kind | artifact |
|---|---|
| `message` | `{channel, text}` |
| `email_draft` | `{to, subject, body}` |
| `document` | `{title, sections[]}` |
| `spreadsheet` | `{sheet, columns[], rows[][]}` |
| `calendar_event` | `{title, start, end, attendees[], joinLink}` |
| `esign` | `{docTitle, signers[], status}` |
| `ticket_update` | `{key, changes[]}` |
| `purchase_order` | `{id, vendor, amount}` |
| `crm_note` | `{accountId, text}` |
| `calendar_block` | `{person, startDay, endDay}` |

Artifacts are built deterministically from solver output and seed facts; **no model call** is made to create them. A UI that meets an unknown `kind` renders a generic key-value card.

### Outcome re-read
`/api/outcome` → `reread[] = [{ system, path, match }]`, one entry per system touched.

## 3a. Additive fields implemented by Person A (heads-up for Person B; all optional to consume)
Implemented in `GET /api/state` (2026-11-28, TASK A3). Existing fields are unchanged.
- top level: `horizonDays` (30), `customers[{id, name}]`
- `tasks[]`: `name`, `requiredSkill`
- `people[]`: `role`, `kind` (`"employee"` | `"contractor"`)
- `presets[]`: `event.unavailable[{personId, startDay, endDay}]` (what the disruption does), and `source{system, eventType, payload}`; the demo `signature` is added with TASK-025
- `chain[]` node `type` values: `task`, `milestone`, `commitment` (the customer commitment), `invoice`
- Error handling: validation failures return HTTP 400 `{error, code:"ValidationError"}`; unexpected failures 500 `{error, code:"InternalError"}`; no input is echoed back.
- Golden solver payloads for building fixtures: `tests/fixtures/solver_golden.json` (per preset: impact, resources, finance, candidate plans, revised plan, applied state, outcome). `Plan.deadlines[].name` is the milestone name; `projectCompletion` keys are `A` and `B`.

Implemented in `POST /api/run/stream` (2026-11-28, TASK A5; Impact node only until A6):
- `failed` carries an extra `code` (`UpstreamModelError` | `BudgetExceeded` | `InternalError`). After a `failed` event the stream **ends: no `done`** is sent (nothing verified exists). Any other node completed earlier stays valid.
- Event order today: `run_started`, `node_started`, `budget` (sent right after the call is reserved), `node_completed`, `done`. `done` currently has `plans: []` and `verdict: null` until the Planner and Verifier land.
- `run_started.event` is the preset's `{unavailable[{personId, startDay, endDay}]}`; `node_completed.evidenceUsed[]` refs look like `preset:<id>`, `task:<id>`, `milestone:<id>`, `commitment:<id>`, `invoice:<id>` (`source` is the system name for the preset, `twin` for seed entities).
- Pre-stream errors are normal JSON: unknown or malformed `presetId` → 400 `ValidationError`; provider env missing → 503 `NotConfigured`. Per-run model-call budget = `MAX_CALLS_PER_RUN` (default 8).
- Streaming headers: `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`.

Implemented in the full graph (2026-11-28, TASK A6 / TASK-011, 012, 013) — supersedes the "Impact node only" notes above:
- Node order: `impact`, then `hr_resource` and `finance` **in parallel** (their `node_started`/`budget`/`node_completed` events may interleave in any order), then `planner`, `verifier`, and on a rejection `planner` (status `revised`) and `verifier` again. So `planner` and `verifier` can each appear twice; a full run is 7 model calls (default budget 8).
- `node_completed.status`: `done`; the first `verifier` is `rejected`; the second `planner` is `revised`.
- `planner` `node_completed` adds `plans[]` (full `Plan` objects; after a rejection the rejected plan has `status:"rejected"` and its revision is included with `revisesPlanId`) and `recommendedPlanId`. `verifier` `node_completed` adds `verdict{planId, decision, reason}`; `derivedFacts` hold the engine's feasibility result per plan.
- The approve/reject decision is the engine's independent re-check of each plan's schedule (`solver.plan_conflicts`); `verdict.reason` is the model's explanation. The Verifier always challenges the naive "reassign to the backup" plan, whatever the Planner recommends.
- `done` is now `{plans[] (4 plans: wait, backup, contractor, backup-revised), verdict (the final one), recommendedPlanId, budget}`. Final plan `status`: `rejected` (backup), `revised` (backup-revised), `verified` (the others, meaning they passed the feasibility check; read `deadlines`/`violatedConstraints` for trade-offs).
- `failed.code` adds `InvalidModelOutput` (the Planner's reply was not a valid choice). A failure in any node ends the stream with no `done`.
- Measured with a real model on 2026-11-28: a full run took about 12 s.

Implemented in execute / outcome / reset (2026-11-28, TASK A7 / TASK-014):
- `POST /api/execute {presetId, approvedPlanId}` returns `{applied: true, twin}` where `twin` is `{presetId, planId, schedule[{taskId, personId, startDay, endDay}], projectCompletion, milestones[{milestoneId, dueDay, completionDay, met}], invoiceEligible, incrementalCost, budgetRemaining, conflicts[]}`. `actions` and `audit` are not included yet (TASK-026).
- The approval gate is server-side: a missing, empty or unknown `presetId`/`approvedPlanId` is 400 `ValidationError` and nothing is applied. A plan the engine finds infeasible (the naive "reassign to the backup" plan) is **409 `PlanRejected`** (new additive error code). `plan-wait`, `plan-backup-revised` and `plan-contractor` can be approved.
- The server keeps no session: execute is a pure function of `(presetId, approvedPlanId)`, so repeating it returns the same twin.
- `POST /api/outcome {presetId, approvedPlanId, twin?}` returns `{match, expected, actual, deltas[{field, expected, actual}]}`. Additive optional `twin`: send back the `twin` you got from `/api/execute`; only its `schedule` is trusted, everything else is re-derived, so a drifted or tampered schedule yields `match:false` with deltas (`projectCompletion.A`, `deadline.<milestone>`, `invoiceEligible`, `conflict`). A `twin` that references unknown tasks, people or days is 400 `ValidationError`. `reread` is not included yet (TASK-026).
- `POST /api/reset` returns the same body as `GET /api/state`.

Implemented in hardening (2026-11-28, TASK A8 / TASK-019/020/021):
- `GET /api/health` now also returns `passcodeRequired: boolean`. When the server sets `DEMO_PASSCODE`, `POST /api/run/stream` (and the deprecated `/api/chat`) require header `X-Demo-Passcode`; a missing or wrong value is 401 `{error:"A valid passcode is required.", code:"Unauthorized"}`. With no passcode configured nothing changes. The UI should show a passcode field only when `passcodeRequired` is true.
- A run that exceeds the server time cap ends with SSE `failed {node:"run", message:"The run took too long and was stopped.", code:"Timeout"}` and no `done`. The model-call budget is `MAX_CALLS_PER_RUN` (default 8; a full run uses 7).
- Request bodies over 64 KB are 413 `{error:"The request is too large.", code:"ValidationError"}`. Every response carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.
- Unhandled server errors are always `{error:"Something went wrong. Please try again.", code:"InternalError"}` with no detail. An `/api/outcome` twin with more than 50 schedule segments is 400 `ValidationError`.
- `/api/chat` is deprecated and will be removed once `static/js/chat.js` and the chat form are gone (B8).
- `GET /dev` is Person A's developer test console. It is **not** part of this contract and not a product surface: do not link to it, depend on it or copy it. It returns 404 on Vercel unless `DEV_CONSOLE=1`.
- Real payload samples (state, full run stream, execute, outcome, the 409 refusal) are in `tests/fixtures/api_samples.json`; use them as the shape reference for `static/mock/*`. Fact tags in those payloads are lowercase `fact|calculated|estimate`.

Implemented for the client-meeting scenario (2026-11-28; seed-schema addition requested and approved by the owner; no new agent):
- A fourth preset `client-meeting-loyalty` ("Client meeting: Orbit Retail asks for a loyalty add-on"). Source: `{system:"crm", eventType:"meeting.notes.logged", payload:{meetingId, accountId, account, title, clientContact, loggedBy, loggedByRole, request, estimateDays, requestedDueDay, quotedValue, currency, sharedWith:["sales","hr","finance"]}}`. It models Business Development logging a client ask that Sales (value), HR (capacity) and Finance (invoice) read from the same record. The same five agents decide; there is no BD or Sales agent.
- `GET /api/state` `presets[].event` gains an optional `demand` (null for the three disruption presets): `{taskId, taskName, days, requiredSkill, defaultAssigneeId, customerId, dueDay, commitment, invoiceAmount, currency}`. For this preset `event.unavailable` is `[]`. Show the request from `demand`; do not treat an empty `unavailable` as "nothing happens".
- The new work (project `P-C`, task `T-C-LOY`, milestone `M-C`, commitment `CM-3`, invoice `INV-2`) exists only inside that scenario. `GET /api/state` `tasks`/`projects`/`milestones` do not contain it, and `POST /api/reset` is unchanged.
- In that scenario `projectCompletion` has a third key `"C"`, `deadlines[]` includes `"Project C delivery"`, `done.plans[].schedule` and `/api/execute` `twin.schedule`/`milestones` include `T-C-LOY` / `M-C`, and the chain is `T-C-LOY → M-C → CM-3 → INV-2`. Render `projectCompletion` as a map; do not hard-code A and B.
- `run_started.event` includes `demand` for that preset only (the three older presets stream exactly the event they always did).
- Plan names differ for the queue option ("Queue behind Dana Reyes's current work"); plan ids and statuses are unchanged (`plan-wait`, `plan-backup` always rejected, `plan-backup-revised`, `plan-contractor`). Results (solver): queue = Project C day 9 (misses due day 8), naive backup rejected (delays the Billing hotfix), revised backup = day 8 for 0 USD (no slack), contractor = day 5 for 1500 USD.
- `GET /mock/crm/meetings` returns the logged meeting record(s) (`X-Simulated: true`); the CRM manifest lists it and the scope `meetings.read`.
- `invoiceAtRisk` in the finance facts is now computed per plan from the invoices whose milestone is missed (identical to before for the old presets, which have one invoice).

Implemented in the tier-1 connectors (2026-11-28, TASK A-INT1 / TASK-024):
- `GET /api/integrations` serves the five tier-1 manifests (`hris`, `tracker`, `erp`, `crm`, `calendar`; each `mode:"simulated"`, `tier:1`, `capabilities:["read"]`); `GET /api/integrations/{id}/sample` works for all five. `lastSync` is a fixed constant (deterministic). Unknown id → 404 `ValidationError`.
- `/mock/*` read endpoints are live exactly as listed in section 3, except `POST /mock/hris/webhooks/leave-approved`, which arrives with TASK-025 (signatures). Every response carries header `X-Simulated: true`. Unknown record → 404 `{error:"Record not found.", code:"ValidationError"}`. Records are addressable by their system id (`NS-142`, `HR-1001`, `ACC-1001`) and by seed id (`T-A-INT`, `PER-DEV1`).
- Additive: `GET /mock/calendar/freebusy?person=<id>&preset=<presetId>` takes an optional `preset` to include that disruption's out-of-office windows. `person` accepts seed id, HRIS id or work email.
- Seed records now carry `source{system, externalId}` (people→hris `HR-100x`, tasks→tracker `NS-142/143/150`, invoices→erp `ERP-INV-90001`, commitments and customers→crm `COM-500x`, `ACC-100x`). These are not yet in `GET /api/state`; tell me if the UI wants them.

## 3b. "Ask the company" and the company data (additive, ADR-006; implemented by Person A)

Separate from the recovery flow above, which is unchanged. The company is a fabricated read-only SQLite database (`data/company/northstar.db`, regenerated by `python -m datahub.generate`; company "today" is 2026-12-01). Same error shape and passcode rules as every other endpoint.

### `POST /api/ask/stream`  body `{ "question": string (1..1000), "history": [{ "role": "user"|"assistant", "content": string (1..1000) }] (0..12) }`  → SSE
Stateless: the client sends the recent conversation each time (the server keeps the last 6 turns). Events, in order of arrival:
- `run_started` `{runId, question, today, budget:{max,used}, toolBudget:{max,used}}`
- `node_started` `{node, role}`; nodes: `orchestrator`, then `specialist_<area>` (`crm|engineering|hr|finance|calendar`, 1 to 3 in parallel), then `synthesizer`. A general question stops after the orchestrator.
- `budget` `{max, used}` (model calls)
- `tool_call` `{node, callId, tool, arguments}` and `tool_result` `{node, callId, tool, ok, rowCount, total?, truncated?, preview[3 rows], error?}`. `callId` is `c1`, `c2`, … per question.
- `node_completed` `{node, role, status:"done", output, budget, ...}` (orchestrator adds `route`; specialist adds `toolCalls`, `area`; synthesizer adds `citations`, `unverifiedNumbers`, `droppedCitations`)
- `answer` `{mode:"company"|"general", text, citations:[{id, tool, arguments, ok, rowCount, total?, truncated?}], unverifiedNumbers:[string], areas:[string]}`. `text` cites evidence as `[c1]`; `general` means "answered without company data" and must be labelled as such in the UI. `unverifiedNumbers` are numbers in the text that match no tool result (the model did its own arithmetic): show a warning.
- `done` `{budget, toolBudget}`
- `failed` `{node, message, code}` with codes `UpstreamModelError`, `InvalidModelOutput`, `BudgetExceeded`, `Timeout`, `InternalError`; never followed by `answer` or `done`; no content is made up.
Per-question limits (env, with defaults): `CHAT_MAX_CALLS` 14 model calls, `CHAT_MAX_TOOL_CALLS` 24 data calls, `RUN_TIMEOUT_SECONDS` 240. `503 NotConfigured` when no model is configured.

### `GET /api/data/...` (read-only; passcode applies)
- `GET /api/data/tools` lists the 22 endpoints with their argument names; `GET /api/data/schema[?table=]` is the data dictionary.
- `GET /api/data/{crm|engineering|hr|finance|calendar}/{function}?{args}` returns `{rows:[...], total?, summary?}` (e.g. `/api/data/crm/list_meetings?date_from=2026-12-02&date_to=2026-12-02&status=scheduled` → `total: 5`). Unknown function 404 `NotFound`; unknown or invalid argument 400 `ValidationError`; non-GET 405. Lists are capped (default 25, max 200 rows); `total` is always the true count.
- Agents also have a guarded `run_sql` (SELECT only, one statement, documented tables, 200 rows, 3 s); it is not exposed as an endpoint.

### Typed events: "Camila is on leave for 6 days" (additive; owner-approved; same ADR-006 family)
A reported event becomes a recovery run on the company database, with the same agents, safety checker and approval gate.
- `POST /api/ask/stream` may answer with two new modes, both with no citations and no model call after routing: `answer.mode:"event"` adds `event:{personId, startDate, workingDays}` (the person is resolved from the name by code; the text says the real dates); `answer.mode:"clarify"` means no run was started and `text` says why (unknown or ambiguous name, days outside 1..15, or no scheduled work disrupted). Other event kinds (resignation, outage) are answered as `general`. Only `leave` is supported.
- `POST /api/event/state` body `{personId, startDate, workingDays}` (extra fields refused) returns `{presetId:"event-leave", state:<same shape as GET /api/state>, calendar:[ISO date of working day 1..20]}`. Errors: 400 `ValidationError` (unknown person, days outside 1..15, start date in the past or beyond the 20-working-day horizon), 409 `NoImpact` (the leave disrupts no scheduled work), 503 `DataUnavailable`.
- `POST /api/run/stream`, `POST /api/execute` and `POST /api/outcome` accept an optional `event` (the same object) together with `presetId:"event-leave"`. The server rebuilds the identical model from the database on every request (no session; deterministic), so the approval gate and outcome re-check work as for the seed scenarios. `event` with any other `presetId` is 400. Without `event` nothing changes.
- Day numbers are working days: day 1 is the company's today (2026-12-01), weekends and holidays are skipped; `calendar` maps number to date.

### Simulated webhooks: six systems, one signed inbox (additive; owner-approved)
Systems tell the AI team about events by themselves. Everything is fabricated, in-process and stateless; no model is called by the inbox. Tag "Simulated webhooks"; responses carry `X-Simulated: true`; the passcode applies to the inbox and the samples.
- `GET /api/webhooks/samples` plays the sending systems. Returns 6 items `{id, source, system, department, eventType, title, description, payload, body, signature, tamperedBody}`. `body` is the exact string to post (canonical JSON); `signature` is `sha256=<hex HMAC-SHA256 of the body>` (demo key, `WEBHOOK_DEMO_SECRET` overrides; it protects nothing real); `tamperedBody` is the same message edited after signing. Payloads use real people, a real completed meeting and a real opportunity from the company database; only the event itself is made up.
- `POST /api/webhooks/{source}` plays the receiver. Header `X-Demo-Signature`, body = the exact `body`. The signature is checked over the raw body **before** anything is read from it. Returns `{source, system, department, eventType, signature:"verified (demo)", summary, fetched:[{system, method, path, summary}], presetId, event}`; `presetId` and `event` are used as-is with `/api/event/state`, `/api/run/stream`, `/api/execute`, `/api/outcome`. Errors: 401 `InvalidSignature` (missing, wrong, or body changed), 404 `NotFound` (unknown source), 400 `ValidationError` (not JSON object, wrong event type, unknown person or client, bad dates, values out of range; the message says what), 409 `NoImpact`, 413 (over 64 KB).
- Sources: `hris` (time off approved, HR), `gcal` (Google Calendar out-of-office; the all-day end date is exclusive), `slack` (`user_change` status with an expiry), `travel` (trip booked and Finance-approved), `meet` (Google Meet transcript ready: the receiver then reads the minutes with a Google Docs `documents.get` call and extracts the client request from the "Decisions and action items" lines; missing parts are named, never guessed), `crm` (Salesforce-style `OpportunityChangeEvent`, stage Closed Won, with delivery days, skill and go-live as custom fields).
- `GET /simulated/docs/v1/documents/{id}` is the simulated Google Docs `documents.get` for the minutes of meeting `doc-mtg-<meetingId>` (Docs API shape: `documentId`, `title`, `body.content[].paragraph.elements[].textRun.content`).
- New event kind. `event` on `/api/event/state`, `/api/run/stream`, `/api/execute`, `/api/outcome` may now also be a client request `{kind:"demand", accountId, title (1..80), skill, days (1..10), dueDate, amount (>0 USD)}` with `presetId:"event-demand"`. The server builds the model from the database (the engineer with that skill and the most open work takes the new task; a backup, a contractor and the budget come from the same department) and the existing solver, agents and approval gate run unchanged. A leave event is the old `{personId, startDate, workingDays}` with `presetId:"event-leave"`. A mismatched `presetId` is 400.

## 4. Open decisions that may touch this contract
- Execution agent solver-only vs model-backed (default solver-only: execution emits no model-generated content).
- Tier-3 connector shapes (TASK-028) are not frozen until that ticket starts.
