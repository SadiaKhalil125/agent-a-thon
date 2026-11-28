# Product Requirements Document — CompanyTwin AI
Project: CompanyTwin AI (organizational digital twin)
Complexity: Standard
Status: Draft
Version: 0.1
Owner: Participant — product/engineering accountable
Last updated: 2026-11-27
Based on: CLAUDE.md context brief (project owner); HACKATHON.md (SSI Agent-A-Thon rules & rubric)

---

## 1. Summary

**Business context.** Most companies run through disconnected departments and tools (sales, engineering, HR, finance, operations). A small operational change — a developer taking leave — can cascade into a slipped task, a delayed milestone, a missed customer commitment and delayed invoice eligibility. Traditional tools record these events in isolation; they do not connect them, investigate the full chain of consequences, reconcile competing departmental priorities, and coordinate a response.

**Problem.** Managers close this coordination gap manually: gathering information from multiple teams, discovering dependencies, comparing options and following up on execution. This causes late decisions, missed commitments and avoidable cost.

**Product idea.** CompanyTwin AI builds a living, connected model of an organization (projects, tasks, people, skills, milestones, customers, invoices and their dependencies) and runs a team of specialized AI agents against that shared model. When a disruptive event is introduced, the agents investigate cross-department impact, compare recovery plans, independently verify feasibility, and — after a human approves a plan — apply the change to the twin and verify the outcome.

**Intended outcome (this release).** One convincing, repeatable, end-to-end demonstration — **project-recovery (Use Case 1)** — that an SSI evaluator can open on a public Vercel URL, run independently, and score highly against the rubric: event → cross-functional investigation → alternative plans → verification → human approval → applied business-state change → verified outcome, with **each agent's work visible** in the UI.

**This document governs the hackathon competition prototype only.** The broader commercial vision in the context brief (connectors, private deployment, permissions, live monitoring) is explicitly out of scope here and is captured under Exclusions and Risks.

---

## 2. Users & Actors

### Human users

| Actor | Role | Access needs (this release) |
|---|---|---|
| **Evaluator / Manager** (primary) | SSI judge or a company manager. Opens the live app, introduces a disruption, observes agent work, compares plans, approves one, sees the verified outcome. | Full use of the single public demo workspace. No login in this release. |
| **Builder** (participant) | Configures the fictional company seed data and deploys. | Repository + Vercel project (outside the running app). |

### System actors

| Actor | Type | Role in the flow |
|---|---|---|
| **CompanyTwin state** | Internal data source | The fictional company model (Northstar Systems): the authoritative operational state the agents read and (on approval) change. |
| **Agent roster** | Internal AI actors | Observer/Memory, Impact Investigator, Delivery Specialist, HR/Resource Specialist, Finance Specialist, Sales/Customer Specialist, Planner/Simulation, Skeptic/Verifier, Execution — coordinated by an Orchestrator. Roles may be combined in implementation; genuine multi-agent collaboration must remain. |
| **LiteLLM gateway** | External system (organizer-provided) | The only model access path. Called server-side with the participant's capped key. |

> Note: Role-based visibility between departments (e.g. sales seeing a delivery estimate but not salaries) is a **commercial-vision** feature, not in this release. See FR-SEC and Exclusions.

---

## 3. Goals & Success Measures

| # | Goal | Measure (this release) | Assumption |
|---|---|---|---|
| G1 | Demonstrate genuine multi-agent orchestration | ≥3 distinct agent roles perform real LiteLLM-backed work and hand findings to one another; the verifier can reject a plan and change the next plan. | "Real work" = runtime tool/model calls, not a single static prompt. |
| G2 | Make orchestration observable | Every agent step is shown in the UI with its role, inputs used, evidence and output. | Evaluators score "visible steps" on Completeness. |
| G3 | Produce a correct, evidence-backed recovery recommendation | Plan comparison shows completion dates, affected deadlines and incremental cost derived from the seed data, with assumptions labeled. | Numbers trace to seed facts + stated calculation, not model guesswork. |
| G4 | Closed loop with human approval | User approves a plan; the twin's state visibly changes; outcome is verified against the selected plan. | Approval is required before any state change. |
| G5 | Repeatable by an independent evaluator | A judge can re-run the scenario and change at least one input to get a correspondingly different result. | No presenter needed; no hidden scripting of agent output. |
| G6 | Stay live and within budget | Public Vercel URL remains usable for the evaluation window; model spend stays within the key's cap. | Abuse/budget protection is in scope (see NFR-OPS). |

---

## 4. Scope & Exclusions

### 4.1 Must-have (MVP)
- A seeded fictional company (Northstar Systems) with projects, tasks, skills, people, availability, task dependencies, milestones, customer commitments and invoice/milestone links — displayed as an understandable initial state.
- At least one **preset disruption** (primary developer unavailable on given working days) the evaluator can trigger; plus the ability to pick among a small set of presets.
- Orchestrated investigation: impact tracing across delivery → HR/resource → finance → sales, with findings and evidence shown per agent.
- Planner produces **≥2 alternative recovery plans** with trade-offs (completion dates, affected deadlines, incremental cost).
- A **Verifier** step that can reject an infeasible/unsupported plan, with its objection shown, causing a revised plan.
- Human **plan selection + approval**, then **execution** that updates the twin, then **outcome verification** against the selected plan.
- Visible agent-activity trail throughout; key server-side; fabricated data only.

### 4.2 Optional / later (only if MVP is solid)
- A second disruption type (e.g. new sales opportunity vs. capacity; supplier delay).
- Custom event entry (evaluator edits event parameters, not just presets).
- A simple relationship/graph view of the twin.
- A synthetic department-visibility demonstration.

### 4.3 Explicit exclusions (not in this release)
- Real client/customer/SSI data of any kind (rules forbid it).
- Authentication, user accounts, multi-tenant isolation, role-based data permissions.
- Live integrations (CRM/ERP/HR/PM/meeting tools), webhooks or live monitoring of external systems.
- Persistent server-side database; durable cross-user state.
- Meeting transcription/recording as a product (meetings are only a possible context source, not the product).
- Personalized financial/investment advice; any real money movement.

### 4.4 Known constraints
- **Platform:** Vercel Hobby. ~5-min/request limit; no reliable server state between requests; ~500 MB bundle; 4.5 MB request/response. (NFR-PERF, NFR-REL.)
- **Models:** LiteLLM organizer gateway only, via the `openai` SDK server-side; model id/gateway **TBD** until key arrives.
- **Stack track:** Python/FastAPI (current repo) or JS/Next.js; Streamlit/Gradio not supported on Vercel. Stack is confirmed at architecture stage, not here.
- **Effort:** individual entry; submission window closes **Mon Nov 30, 2026, 2:00 PM PKT** per HACKATHON.md (context brief says Sun Nov 29 — to be confirmed; non-blocking).

---

## 5. Main Workflows / User Journeys

### Flow A — Project-recovery demonstration (primary, MVP)
**Trigger:** Evaluator opens the app and selects a disruption preset.
**Actors:** Evaluator; Orchestrator + agent roster; CompanyTwin state; LiteLLM.

1. **See initial state.** App shows Northstar Systems: projects, task dependencies, people/skills/availability, milestones, customer commitments, invoice links, recovery budget. (FR-TWIN)
2. **Introduce event.** Evaluator triggers a preset, e.g. "Primary developer unavailable, working days 1–5." (FR-EVENT)
3. **Observe + scope.** Observer relates the event to the model and flags what must be investigated. (FR-ORCH, FR-IMP)
4. **Impact investigation.** Impact Investigator traces affected integration work, dependent QA, the milestone, the customer commitment and the dependent invoice, following the model's real relationships. (FR-IMP)
5. **Specialist evidence.** HR/Resource checks qualified alternatives and existing workload; Finance assesses incremental cost vs. recovery budget and milestone/invoice exposure; Sales checks the customer commitment. Each shows evidence. (FR-IMP, FR-ORCH)
6. **Plan alternatives.** Planner combines findings into ≥2 recovery plans with completion dates, affected deadlines and incremental direct cost; trade-offs exposed. (FR-PLAN)
7. **Verification.** Skeptic/Verifier independently checks feasibility and assumptions; may **reject** a plan (e.g. a reassignment that ignores the backup's existing Project B load), which triggers a revised plan. (FR-VER)
8. **Approve.** Evaluator reviews the comparison and approves one plan. (FR-EXEC)
9. **Execute.** Execution agent applies the approved changes to the twin (reassignments/schedule). (FR-EXEC)
10. **Verify outcome.** System re-checks the new state against the selected plan and reports whether it matches. (FR-EXEC)

**Material exception paths:**
- No feasible plan preserves all commitments → system presents the least-bad options with the violated constraints named, not a false "all green." (AC-PLAN, AC-VER)
- LiteLLM unavailable / budget exhausted / timeout → app degrades to a clear, honest status rather than fabricating agent output. (FR-ORCH, NFR-REL, NFR-OPS)
- Evaluator approves nothing → state is unchanged; no execution occurs. (AC-EXEC)

### Flow B — Re-run / change an input (judge repeatability)
**Trigger:** Evaluator re-runs, or (optional) changes a preset parameter.
Agents produce a correspondingly different investigation/plan from the same deterministic seed; no cached or scripted result is replayed as if freshly computed. (FR-EVENT, NFR-REL, G5)

---

## 6. Functional Requirements

> Priorities: **P1** = MVP must-have; **P2** = strengthen-if-stable; **P3** = optional.

### Domain TWIN — Organizational model
- **FR-TWIN-001 (P1): Seeded company model.** The system loads a fictional company (Northstar Systems) with projects, tasks, task dependencies, people, skills, availability windows, milestones, customer commitments, invoice-to-milestone links and a recovery budget, from version-controlled fabricated seed data.
- **FR-TWIN-002 (P1): Initial-state presentation.** The system presents the initial state so a first-time evaluator can understand the connected commitments (what work supports which milestone, which milestone gates which invoice).
- **FR-TWIN-003 (P2): Relationship visibility.** The system makes the dependency relationships inspectable (e.g. from a milestone back to the tasks and people it depends on).

### Domain EVENT — Disruption introduction
- **FR-EVENT-001 (P1): Preset disruptions.** The evaluator can introduce a disruption from a small preset set; the primary preset is "primary developer unavailable on working days 1–5."
- **FR-EVENT-002 (P1): Deterministic re-run.** Re-running the same preset against the same seed yields consistent inputs to the agents (randomness, if any, is seeded), so results are reproducible and explainable.
- **FR-EVENT-003 (P3): Custom event parameters.** The evaluator can edit event parameters (who, which days) within bounds, and the investigation reflects the change.

### Domain ORCH — Orchestration & observability
- **FR-ORCH-001 (P1): Coordinated multi-agent run.** An orchestrator sequences the relevant agents for the event; not every event invokes every agent.
- **FR-ORCH-002 (P1): Real agent work.** Each participating agent performs a runtime LiteLLM-backed reasoning/tool step over real model inputs; no agent output is hard-coded or scripted.
- **FR-ORCH-003 (P1): Visible step trail.** The UI shows, per agent step: the role, the inputs/evidence it used, and its output/finding, in the order they occurred.
- **FR-ORCH-004 (P1): Findings influence each other.** Downstream agents consume upstream findings; a verifier rejection changes the next planner output (not merely displayed side by side).
- **FR-ORCH-005 (P2): Honest degradation.** If a model/tool call fails, the step is shown as failed/unavailable; the system never presents fabricated agent activity.

### Domain IMP — Impact investigation
- **FR-IMP-001 (P1): Dependency tracing.** Given the event, the Impact Investigator identifies affected tasks, dependent tasks (e.g. QA after integration), the milestone, the customer commitment and the dependent invoice, by following the model's actual relationships.
- **FR-IMP-002 (P1): Resource reality.** The HR/Resource step considers a candidate replacement's existing assignments and availability rather than treating people as unlimited.
- **FR-IMP-003 (P1): Financial exposure.** The Finance step relates the delay to milestone acceptance and invoice eligibility, and compares any incremental cost to the recovery budget.
- **FR-IMP-004 (P1): Evidence linkage.** Each finding cites the specific model facts it used.

### Domain PLAN — Alternatives & simulation
- **FR-PLAN-001 (P1): Alternative plans.** The Planner produces ≥2 recovery alternatives for the event.
- **FR-PLAN-002 (P1): Trade-off comparison.** Each plan states projected completion for affected projects, which deadlines it meets or misses, and incremental direct cost, in a comparable form.
- **FR-PLAN-003 (P1): Labeled certainty.** Calculated figures are tied to seed facts and a stated calculation; uncertain estimates are labeled as estimates, not facts.
- **FR-PLAN-004 (P2): Constraint honesty.** When no plan satisfies every commitment, the Planner names the violated constraints instead of implying all are met.

### Domain VER — Verification (skeptic)
- **FR-VER-001 (P1): Independent challenge.** A Verifier independently reviews plans for feasibility and unsupported assumptions.
- **FR-VER-002 (P1): Reject-and-revise.** The Verifier can reject a plan with a stated reason; a rejection causes a revised plan that addresses the objection.
- **FR-VER-003 (P1): Visible verdict.** The Verifier's verdict and reasoning are shown to the evaluator.

### Domain EXEC — Approval, execution & outcome verification
- **FR-EXEC-001 (P1): Human approval gate.** No change is applied to the twin until the evaluator explicitly approves a specific plan.
- **FR-EXEC-002 (P1): Apply approved plan.** On approval, the Execution agent applies the plan's changes (assignments/schedule) to the twin state for the session.
- **FR-EXEC-003 (P1): Outcome verification.** After execution, the system re-evaluates the new state against the selected plan and reports match / mismatch.
- **FR-EXEC-004 (P1): Fabricated-only, reversible.** Execution affects only the fictional in-session state; it never touches real clients, accounts or external services, and the demo can be reset.

### Domain UI — Presentation
- **FR-UI-001 (P1): Guided demo journey.** The UI leads the evaluator through state → event → investigation → plans → verification → approval → outcome without a presenter.
- **FR-UI-002 (P1): Plan comparison view.** Alternatives are shown side by side with their trade-offs.
- **FR-UI-003 (P2): Reset/re-run control.** The evaluator can reset to initial state and run again.

### Domain SEC — Security & data boundary
- **FR-SEC-001 (P1): Server-side key.** All LiteLLM calls happen server-side; the key is never exposed to the browser or committed to the repository.
- **FR-SEC-002 (P1): Fabricated data only.** Only fabricated/public data is present anywhere in the app or repo.
- **FR-SEC-003 (P3): Synthetic permission demo.** (Optional) A visibly synthetic illustration that a department sees only what it is authorized to — clearly labeled as a concept, not real access control.

---

## 7. Acceptance Criteria

> Format: `AC-<DOMAIN>-<FR#>-<n>`. Each relates to the FR of the same number.

- **AC-TWIN-001-01:** Loading the app shows the seeded company with at least the entities in FR-TWIN-001, sourced from committed seed files.
- **AC-TWIN-002-01:** From the initial view, the link milestone → gating tasks → gated invoice is discoverable without reading code.
- **AC-EVENT-001-01:** Selecting the primary preset injects the "developer unavailable, days 1–5" event and starts an orchestrated run.
- **AC-EVENT-002-01:** Running the same preset twice on the same seed yields the same agent inputs and a materially consistent result.
- **AC-ORCH-002-01:** Each agent step corresponds to an observed runtime model/tool call (verifiable in server logs), not a constant string.
- **AC-ORCH-003-01:** The UI lists agent steps in order with role, evidence used and output for each.
- **AC-ORCH-004-01:** A Verifier rejection is followed by a different Planner output that references the objection.
- **AC-ORCH-005-01:** When a model call fails, the corresponding step is marked failed/unavailable and no fabricated content is shown in its place.
- **AC-IMP-001-01:** For the primary preset, the investigation output includes the affected integration task, the dependent QA, the milestone, the customer commitment and the dependent invoice.
- **AC-IMP-002-01:** A proposed reassignment accounts for the backup's existing Project B assignment (does not double-book).
- **AC-IMP-003-01:** The finance finding states the milestone/invoice exposure and compares incremental cost to the recovery budget.
- **AC-PLAN-001-01:** At least two distinct recovery plans are produced for the primary preset.
- **AC-PLAN-002-01:** Each plan shows projected completion for the affected projects, deadline impact, and incremental cost in a comparable layout.
- **AC-PLAN-003-01:** Every numeric claim in a plan is accompanied by its source facts or a stated calculation; estimates are labeled.
- **AC-PLAN-004-01:** When commitments conflict, at least one plan explicitly names the constraint it violates.
- **AC-VER-002-01:** The Verifier rejects at least one infeasible/unsupported candidate in the primary scenario and the system revises it.
- **AC-VER-003-01:** The Verifier's verdict and reason are visible to the evaluator.
- **AC-EXEC-001-01:** No twin state changes until the evaluator approves a specific plan.
- **AC-EXEC-002-01:** After approval, the twin reflects the approved plan's assignment/schedule changes.
- **AC-EXEC-003-01:** The outcome check reports whether the new state matches the selected plan, including any mismatch.
- **AC-EXEC-004-01:** A reset returns the app to the seeded initial state; no external system is contacted during execution.
- **AC-UI-001-01:** An evaluator with no briefing can complete Flow A end to end using only on-screen guidance.
- **AC-SEC-001-01:** No LiteLLM key appears in client-delivered assets, network responses to the browser, or the repository.
- **AC-SEC-002-01:** A repository/app scan surfaces no real personal/customer/SSI data.

---

## 8. Acceptance Tests

> `AT-<DOMAIN>-<FR#>-<n>`. All are **Not implemented** until the execution phase. "To be automated during implementation" unless marked manual.

#### AT-TWIN-001-01: Seed loads
Relates to: FR-TWIN-001; AC-TWIN-001-01 · Type: Integration · Preconditions: committed seed files · Steps: load initial-state endpoint/page · Expected: all required entity types present and internally consistent (every invoice links to a milestone; every milestone to ≥1 task). · Execution: automated.

#### AT-TWIN-002-01: Dependency is discoverable
Relates to: FR-TWIN-002; AC-TWIN-002-01 · Type: Manual/E2E · Steps: from initial view, trace a milestone to its gating tasks and gated invoice · Expected: path is visible in UI. · Execution: manual checklist.

#### AT-EVENT-001-01: Preset starts a run
Relates to: FR-EVENT-001; AC-EVENT-001-01 · Type: Integration · Steps: trigger primary preset · Expected: orchestration begins; event parameters match the preset. · Execution: automated.

#### AT-EVENT-002-01: Deterministic re-run
Relates to: FR-EVENT-002; AC-EVENT-002-01 · Type: Integration · Steps: run primary preset twice on same seed, compare agent inputs/derived figures · Expected: identical inputs; materially consistent plan figures. · Execution: automated (compares the deterministic, non-model-generated derived facts).

#### AT-ORCH-002-01: Real model calls
Relates to: FR-ORCH-002; AC-ORCH-002-01 · Type: Integration · Steps: run scenario with LiteLLM configured; inspect server call log/count · Expected: one runtime call per agent step; no step returns a hard-coded constant. · Execution: automated with a gateway test double asserting call occurrence.

#### AT-ORCH-003-01: Visible ordered steps
Relates to: FR-ORCH-003; AC-ORCH-003-01 · Type: E2E · Steps: run scenario · Expected: UI shows ordered steps each with role, evidence, output. · Execution: automated (DOM/DOM-equivalent assertions).

#### AT-ORCH-004-01: Rejection changes the plan
Relates to: FR-ORCH-004, FR-VER-002; AC-ORCH-004-01, AC-VER-002-01 · Type: Integration · Steps: force/encounter a rejectable plan · Expected: subsequent plan differs and references the objection. · Execution: automated with a seeded rejectable candidate.

#### AT-ORCH-005-01: Honest failure
Relates to: FR-ORCH-005; AC-ORCH-005-01 · Type: Integration / negative · Steps: simulate gateway failure mid-run · Expected: step marked failed/unavailable; no fabricated output; safe message. · Execution: automated with an injected failure.

#### AT-IMP-001-01: Full impact chain
Relates to: FR-IMP-001; AC-IMP-001-01 · Type: Integration · Steps: run primary preset · Expected: output enumerates integration task, dependent QA, milestone, customer commitment, dependent invoice. · Execution: automated assertion against known seed chain.

#### AT-IMP-002-01: No double-booking
Relates to: FR-IMP-002; AC-IMP-002-01 · Type: Integration · Steps: inspect any plan reassigning the backup · Expected: plan respects the backup's Project B days or flags the conflict. · Execution: automated.

#### AT-IMP-003-01: Finance exposure
Relates to: FR-IMP-003; AC-IMP-003-01 · Type: Integration · Steps: read finance finding · Expected: states milestone/invoice exposure and incremental-cost-vs-budget. · Execution: automated.

#### AT-PLAN-001-01: Two+ plans
Relates to: FR-PLAN-001; AC-PLAN-001-01 · Type: Integration · Expected: ≥2 distinct plans. · Execution: automated.

#### AT-PLAN-002-01: Comparable trade-offs
Relates to: FR-PLAN-002; AC-PLAN-002-01 · Type: Integration · Expected: each plan exposes completion/deadline-impact/cost in comparable fields. · Execution: automated.

#### AT-PLAN-003-01: Labeled numbers
Relates to: FR-PLAN-003; AC-PLAN-003-01 · Type: Manual/Integration · Expected: numeric claims carry source/calculation; estimates labeled. · Execution: automated where fields are structured; manual spot-check on prose.

#### AT-PLAN-004-01: Constraint honesty
Relates to: FR-PLAN-004; AC-PLAN-004-01 · Type: Integration · Steps: run a scenario variant where not all deadlines can hold · Expected: a plan names the violated constraint. · Execution: automated with a constrained seed variant (P2).

#### AT-VER-003-01: Visible verdict
Relates to: FR-VER-003; AC-VER-003-01 · Type: E2E · Expected: verifier verdict + reason shown. · Execution: automated.

#### AT-EXEC-001-01: Approval required
Relates to: FR-EXEC-001; AC-EXEC-001-01 · Type: Integration / security · Steps: attempt to reach executed state without approval · Expected: no state change occurs. · Execution: automated.

#### AT-EXEC-002-01: Apply plan
Relates to: FR-EXEC-002; AC-EXEC-002-01 · Type: Integration · Steps: approve a plan · Expected: twin reflects the plan's changes. · Execution: automated.

#### AT-EXEC-003-01: Outcome verification
Relates to: FR-EXEC-003; AC-EXEC-003-01 · Type: Integration · Expected: post-execution check reports match/mismatch vs selected plan. · Execution: automated.

#### AT-EXEC-004-01: Reset & no external calls
Relates to: FR-EXEC-004; AC-EXEC-004-01 · Type: Integration · Expected: reset restores seed; no outbound call except LiteLLM gateway during a run. · Execution: automated (network assertion).

#### AT-UI-001-01: Unassisted end-to-end
Relates to: FR-UI-001; AC-UI-001-01 · Type: Manual/E2E · Expected: a fresh evaluator completes Flow A using on-screen guidance only. · Execution: manual usability pass + automated smoke of the happy path.

#### AT-SEC-001-01: No key leakage
Relates to: FR-SEC-001; AC-SEC-001-01 · Type: Security · Steps: inspect client bundle, browser network, repo history for the key/`sk-` · Expected: none found. · Execution: automated repo scan + manual network check.

#### AT-SEC-002-01: No real data
Relates to: FR-SEC-002; AC-SEC-002-01 · Type: Security/manual · Expected: no real personal/customer/SSI data present. · Execution: manual review + scan.

---

## 9. Nonfunctional Requirements

### NFR-PERF — Performance & platform limits
- **NFR-PERF-001 (P1):** No single HTTP request may rely on exceeding Vercel's ~5-minute limit; long orchestration is split into bounded per-step requests or streamed. · AC-PERF-001-01: the full scenario completes without any single request timing out. · AT-PERF-001-01 (Integration): measure per-request duration under the scenario; each < limit.
- **NFR-PERF-002 (P2):** Request/response payloads stay within ~4.5 MB; seed and step payloads are bounded.

### NFR-REL — Reliability & statelessness
- **NFR-REL-001 (P1):** The app does not depend on server memory persisting between requests; scenario/run state is carried in the client/session or reconstructed from the deterministic seed. · AC-REL-001-01: a run survives being served by independent stateless invocations. · AT-REL-001-01 (Integration): simulate no shared server memory; run still completes.
- **NFR-REL-002 (P1):** The app stays deployed and usable for the evaluation window without a presenter or a local machine. · Verification: manual deployment check (AT-REL-002-01, manual).

### NFR-SEC — Security
- **NFR-SEC-001 (P1):** Secrets live only in Vercel env vars / local `.env.local` (gitignored); never in code, client, logs or screenshots. (Reinforces FR-SEC-001.) · AT-SEC-001-01.
- **NFR-SEC-002 (P1):** Server validates inputs at its boundaries (event selection, approval actions) and fails safely with non-revealing messages. · AC-SEC-sec2-01 · AT-SEC-sec2-01 (Integration/negative): malformed event/approval requests are rejected safely.

### NFR-OPS — Budget & abuse protection
- **NFR-OPS-001 (P1):** The public app limits model spend against the capped key (e.g. bounded steps per run; optional lightweight rate limit or passcode as a stretch) so a public URL cannot silently exhaust the budget. · AC-OPS-001-01: a single run has a bounded, known maximum number of model calls. · AT-OPS-001-01 (Integration): a run never exceeds the configured call budget.
- **NFR-OPS-002 (P2):** Server logs capture run/step status and provider errors without logging secrets or full payloads, enough to diagnose a failed demo.

### NFR-USE — Usability & honesty of presentation
- **NFR-USE-001 (P1):** The UI distinguishes facts (seed data), calculated outcomes, and model predictions; it does not present model reasoning as an audit trail of guaranteed truth. · AT-USE-001-01 (Manual): review that labels/sections convey this distinction.
- **NFR-USE-002 (P2):** Basic accessibility for the demo UI: keyboard operability of primary controls, sufficient contrast, labeled controls. · AT-USE-002-01 (Manual a11y checklist).

### NFR-MAINT — Maintainability
- **NFR-MAINT-001 (P2):** Seed data and agent prompts/roles are defined in clearly separated, version-controlled files so a judge-facing scenario change is a data edit, not a code rewrite.

---

## 10. Integrations & Data

| Item | Detail |
|---|---|
| **LLM gateway (OpenAI-compatible)** | Only external dependency. Server-side calls to any OpenAI-compatible gateway, configured in the environment; the organizer **LiteLLM gateway for submission** (capped spend). Config: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (legacy `LITELLM_*` accepted). Provider is config, not code. |
| **Company seed data** | Fabricated Northstar Systems model in committed files (e.g. JSON). Owned by the app; no external source. Fields: projects, tasks (effort, type: integration/QA, deps), people, skills, availability windows, milestones (due working-day, acceptance), customer commitments, invoices (amount, gated-by milestone), recovery budget, contractor option (rate, availability). |
| **Data ownership & retention** | All data is fabricated and ephemeral; execution changes live only in session state and reset on demand. No persistent store, no PII, no retention obligation. |
| **Secrets** | Only the LiteLLM key; stored in env vars, never in repo/knowledge/docs. |
| **Privacy** | No personal data collected from evaluators; no analytics requirement in this release. |

**Illustrative seed scenario (from the context brief, to be used as the primary preset — fabricated, assumptions stated):** Project A milestone due working-day 6; acceptance makes an $8,000 invoice eligible; Project A needs 4 days integration + 2 days QA; primary developer unavailable days 1–5; a qualified backup is free days 2–5 but is on Project B days 2–3 (Project B due day 4); a qualified contractor is available from day 1 at a fixed incremental $1,500; recovery budget $2,000; QA capacity available when integration finishes. These numbers are fabricated planning inputs, not predictions.

---

## 11. Risks & Assumptions

| ID | Type | Item | Blocking? | Handling |
|---|---|---|---|---|
| R1 | Assumption | LiteLLM model id/gateway unknown until key arrives. | No | Build against the three env vars; "Ask"-style status until configured; confirm model via `/models`. |
| R2 | Risk | Vercel 5-min/stateless limits break a long single-call orchestration. | No | Architecture must split steps per request or stream; carry state client-side/seed-derived. (NFR-PERF/REL.) |
| R3 | Risk | Public URL + capped key → budget exhaustion/abuse. | No | Bounded calls per run; optional rate limit/passcode. (NFR-OPS.) |
| R4 | Risk | "Fake orchestration" (scripted logs) would fail the rubric and the owner's intent. | No | FR-ORCH-002/005 require real calls and honest failure; AT verifies call occurrence. |
| R5 | Risk | Model may assert unsupported numbers. | No | Derive figures deterministically from seed; model explains, does not invent; label estimates. (FR-PLAN-003.) |
| R6 | Assumption | Single demo workspace, no auth, fabricated data. | No | Documented exclusion; escalate tier only if real data/auth added. |
| R7 | Open | Submission deadline discrepancy (Nov 29 vs Nov 30 2:00 PM PKT). | No | Treat Nov 30 2:00 PM PKT (HACKATHON.md) as working deadline; confirm with organizers. |
| R8 | Open | Stack choice (FastAPI vs Next.js) not yet fixed. | No | Decided at architecture stage; current repo is FastAPI. |

No blocking unknowns prevent a responsible architecture stage.

---

## 12. Release / Product Acceptance Boundary

The MVP is acceptable for submission when, independent of implementation detail:
1. An evaluator opens the public Vercel URL and, with no presenter, completes **Flow A** end to end (state → event → investigation → ≥2 compared plans → a visible verifier rejection-and-revision → approval → applied state change → verified outcome).
2. All **P1** acceptance tests pass or have recorded, honest manual verification; none are faked.
3. **FR-ORCH-002** holds: agent steps are real runtime model calls, visibly ordered with evidence (not scripted).
4. **FR-SEC-001/002** hold: no key in client/repo; no real data (incognito + scan clean).
5. The app runs within the key's budget for a normal run and stays deployed for the evaluation window.
6. The submission package is ready: public GitHub repo, short public `*.vercel.app` URL, ≤600-char summary.

Optional (P2/P3) items do not gate acceptance and are only pursued once P1 is solid.

---

## 13. Open Questions

- **OQ1 (non-blocking):** Confirmed submission cutoff — Nov 29 or Nov 30 2:00 PM PKT? (R7)
- **OQ2 (to resolve at architecture):** FastAPI (current repo) vs Next.js? (R8)
- **OQ3 (non-blocking):** Is a second disruption type (Flow B variety) wanted for the submission, or kept as stretch? Affects P2 scope only.
- **OQ4 (non-blocking):** Any passcode/rate-limit expectation for the public URL beyond bounded calls? (NFR-OPS.)

---

### Traceability note
Every P1 FR has ≥1 AC and ≥1 AT above. NFRs carry their own AC/AT. Full FR/NFR → AC → AT → TASK matrix will be completed in `phases.md` (Stage 5); no delivery tickets are defined at PRD stage.
