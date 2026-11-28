# Engineering & AI Rules — CompanyTwin AI
Project: CompanyTwin AI (organizational digital twin)
Complexity: Standard
Status: Draft
Version: 0.3
Owner: Participant
Last updated: 2026-11-28
Based on: docs/PRD.md v0.2, docs/architecture.md v0.3, docs/design.md v0.1

> v0.3: adds **simulated-connector rules** (§3, §5, §7, §8) and the **two-person parallel working rules** (§9a). See `docs/BUILD_PLAN.md` v2.

> v0.2: orchestration is **LangGraph** (architecture ADR-002/003 revised). Dependency and model-call rules updated below; everything else unchanged.

> These are enforceable constraints for this repo, derived from `04_ENGINEERING_STANDARDS.md` and the approved docs. Commands marked **(confirm at scaffold)** are resolved in the Phase-0 setup ticket, not assumed to exist yet.

---

## 1. Authority & scope

- **Source of truth order:** approved PRD → architecture → design → this file → phases/ticket → memory. On any conflict, stop and surface it; do not resolve silently.
- **Tier:** Standard. No controls beyond the approved scope (no auth, DB, microservices, DR).
- **Agent role:** the AI implementer (Claude Code / Cursor in Accept-Edits mode) works **one approved `TASK-*` at a time**, within the boundaries in §10. Escalate anything requiring approval to the owner.
- **Hackathon guardrails are hard rules:** key server-side only, fabricated/public data only, real agentic behavior (no scripted output), live on Vercel.

---

## 2. Code conventions

- **Language:** Python 3.12, type-hinted at module boundaries (function signatures, Pydantic models). Prefer explicit types over `Any`.
- **Format & lint:** **Ruff** (lint + format) is the single tool. `ruff check .` and `ruff format --check .` must pass. (confirm config at scaffold)
- **Types:** Pydantic v2 models for every request/response and for `RunContext`; static type check with **mypy** or **pyright** on `twin/`, `agents/`, `orchestration/` at minimum. (confirm which at scaffold)
- **Naming:** `snake_case` functions/modules, `PascalCase` classes, `UPPER_SNAKE` constants; endpoints `/api/<area>`; test files `test_<unit>.py`.
- **Module layout & dependency direction (from architecture §4):** `api → orchestration → {agents, twin}`; `agents → twin` (read only); `twin.solver` is a **pure leaf**. No upward or circular imports. A lint/import rule should guard this. (confirm at scaffold)
- No dead code, commented-out blocks, or unexplained constants committed.

---

## 3. Implementation rules

- **Small, coherent changes** scoped to the active ticket; never touch unrelated files.
- **Separation of concerns is a hard boundary, not a preference:**
  - `twin.solver` computes **all** numbers (completion days, deadline impact, cost, eligibility, outcome) and has **no** model calls and no I/O beyond its inputs/return value.
  - `agents.*` **never** compute quantitative results; they build prompts, call the LiteLLM wrapper, and parse judgment/narrative + a chosen option id. (ADR-001)
  - `api.*` validates, enforces budget, and shapes responses; it **never** calls LiteLLM directly.
- **Validation at boundaries:** every request body is a Pydantic model; reject unknown `presetId`/`stepId`/`approvedPlanId`; bound `transcript`/`workingTwin` size.
- **Contract enforcement:** the step/plan response shape is the contract (architecture §7); changing it is a contract change (§10 approval).
- **One model call per graph node** — never make an unbounded number of calls. The whole run is capped by a **node/call budget** enforced in the graph (NFR-OPS-001). Parallel specialist nodes (LangGraph fan-out) are allowed but each still counts one call against the budget.
- **Orchestration is a LangGraph `StateGraph`** (`orchestration/graph.py`); the verifier→planner revision is a **conditional edge** capped at one revision. Nodes call `twin.solver` for numbers; the model is reached only through `agents/llm.py` (`ChatOpenAI` → LiteLLM).
- **Stateless:** no reliance on server memory between requests; derive from seed + client `RunContext` (NFR-REL-001).
- **Simulated connectors (`integrations/`, v0.3):**
  - Dependency direction: `integrations → twin(read)` only; it must not import `agents`, `orchestration` or `api`. `api`, `orchestration` and `agents` may call it.
  - **No outbound network, no real credentials, no persistence** in `integrations/`; no HTTP client library imported there. Calls from nodes are in-process; `/mock/*` is just the same handlers over HTTP.
  - **No model calls and no number computation** in `integrations/`: read adapters are views over the seed; ActionBuilders format solver output and seed facts into artifacts. Every figure shown in an artifact comes from `twin/solver.py`.
  - Every write/action carries an **idempotency key** (same key returns the same result) and every call/action produces an **audit** entry; every manifest has `mode:"simulated"`.
  - A failed connector call yields a failed `integration_call` and **no fabricated data**.
  - Use category names and neutral glyphs, never real vendor logos or claims of a real connection.

---

## 4. Dependency policy

- **Approved baseline:** `fastapi`, `uvicorn`, `openai`, `python-dotenv`, `pydantic`, **`langgraph`, `langchain-openai`** (pulls `langchain-core`). **Dev:** `pytest`, `ruff`, `httpx`, `mypy`.
- **Pinning:** versions pinned in `requirements.txt`. **Watch the deployed function size against Vercel's limit** — the langchain stack is non-trivial (AR6); **no** PyTorch/TensorFlow/transformers or other heavy ML; models are reached only via the gateway.
- **New dependency = owner approval** (§10): justify need, check it's maintained, confirm it doesn't pull heavy transitive weight or break the bundle limit. Prefer the standard library.
- Treat all third-party packages and all model output as **untrusted**.

---

## 5. Data handling

- **No database, no persistence.** Seed lives in `data/seed/northstar.json`, read-only, validated on load (every invoice→milestone, every milestone→≥1 task, availability well-formed).
- **Fabricated/public data only** anywhere in repo, app, logs, tests, or fixtures (FR-SEC-002). No real client/customer/SSI data, ever, including for testing.
- **Execution** mutates only the client's in-session working twin via the solver; **reset** restores the seed (FR-EXEC-004). Nothing is shared across users or requests.
- No PII is collected from evaluators; no analytics in this release.
- **Connector payloads** (emails, documents, spreadsheets, chat messages, e-sign envelopes) use fabricated Northstar data only; no real names, addresses, domains or account numbers (use reserved example domains such as `example.com`).

---

## 6. Errors & observability

- **Error taxonomy:** `ValidationError` (400), `NotConfigured` (503, LiteLLM env missing), `BudgetExceeded` (429/refused), `UpstreamModelError` (step `failed`), `InternalError` (500). Client sees `{error, code}` with a **safe, generic** message — no stack traces, no internal detail (NFR-SEC-002).
- **No fabrication on failure:** a failed model call yields a `failed` step with no generated content (FR-ORCH-005). Never synthesize an agent result to fill a gap.
- **Retry:** the LiteLLM wrapper retries **at most once** on transient error, then fails the step (protects budget and the 5-min ceiling).
- **Structured logs** per run/step: `runId, stepId, role, duration_ms, provider_status, call_count, budget_remaining`. **Never** log the key, full prompts/responses, or payloads (NFR-OPS-002).

---

## 7. Security requirements

- **Secrets:** `LLM_BASE_URL/API_KEY/MODEL` (legacy `LITELLM_*` accepted; optional `DEMO_PASSCODE`, `MAX_CALLS_PER_RUN`) come from env only, resolved in `config.py`; `.env.local` stays gitignored; never commit, log, screenshot, or send to the browser. The provider is chosen in the environment (the LiteLLM gateway for submission) — a change of values, not code or repo content. Only `/api/health` exposes the boolean `llm_configured` (FR-SEC-001).
- **Server-side authorization of the one guarded action:** `/api/execute` must verify `approvedPlanId` was produced in the same run before applying changes (FR-EXEC-001). No identity auth by design.
- **Input validation** at every external boundary (browser bodies, and defensive parsing of model output — model text is data, never executed).
- **Budget/abuse:** enforce ≤1 model call per request and a fixed max steps per run; **recommended P2 hardening:** `DEMO_PASSCODE` or a lightweight per-IP throttle (NFR-OPS-001). Document the residual risk honestly.
- **Inbound simulated webhooks** carry a demo HMAC signature verified server-side with a **non-secret demo key held in code/seed** (it protects nothing real); unverifiable payloads are rejected with `{error, code}`. Never reuse the LLM key or any real secret for this.
- **Write scopes** shown in manifests are exercised only after `/api/execute` validated `approvedPlanId`; read-only before approval.
- Security-test selection follows relevant OWASP input/secret/auth-gate cases (AT-SEC-*), not arbitrary compliance claims.

---

## 8. Test & verification policy

- **Framework:** `pytest` + FastAPI `TestClient`/`httpx`. (confirm at scaffold)
- **Required by tier (Standard):**
  - **Unit** — `twin.solver` math is mandatory and high-coverage (pure, deterministic): AT-TWIN-001-01, AT-IMP-001/002/003, AT-PLAN-001/002/004, AT-EXEC-002/003.
  - **Integration** — graph node execution + the conditional verifier→planner edge, budget cap, approval gate, honest node failure, deterministic re-run, no-external-call: AT-ORCH-002/003/004/005, AT-EVENT-001/002, AT-EXEC-001/004, AT-REL-001, AT-OPS-001, AT-PERF-001. Model boundary uses an **injected fake chat model** (LangChain fake/stub — asserts node invocation and routing; can simulate failure) — never a real paid call in unit/integration.
  - **Connectors (P2)** — `tests/test_integrations.py`: manifests valid and `mode:"simulated"`, artifact shapes match `docs/contracts.md`, idempotent replay, audit ordering, bad-signature rejection, no outbound network, no persistence: AT-INT-001…006, AT-INT-sec-01.
  - **E2E/smoke** — happy path of Flow A: AT-UI-001-01 (+ manual usability pass).
  - **Security** — key/`sk-` scan + real-data review: AT-SEC-001/002.
- **Evidence rule:** a passing test is an **observed run**, reported with the command and result. A written test is not a passed test. If a check cannot run (e.g. no gateway), report **`Not run`** — never invent a result (this is also §10 Forbidden).
- **Commands (confirm exact at scaffold):** `ruff check . && ruff format --check . && mypy . && pytest -q`.
- **Regression:** the solver and step-contract tests must stay green on every ticket; a red test blocks "done."

---

## 9. Git & CI policy

- **Branches:** short-lived `feat/TASK-NNN-brief` / `fix/TASK-NNN-brief` off `main`; no long-lived phase branches. Commit messages include the `TASK-NNN` id.
- **Main:** auto-deploys to Vercel on push — so `main` must stay deployable; prefer PRs even as a solo dev, squash-merge.
- **CI (confirm at scaffold):** a GitHub Actions workflow runs `ruff`, type check, and `pytest` on PR/push. A failing CI check blocks merge.
- **Key hygiene in CI/history:** no secret in any commit; a pre-submit scan for `sk-` must come back empty (AT-SEC-001-01).

---

## 9a. Two-person parallel working rules (v0.3)

- Two people work in parallel with separate Cursor agents; the split, file ownership and sync points are in `docs/BUILD_PLAN.md` v2 §4 and §9.
- **Person A (engine)** owns `twin/ data/seed/ agents/ orchestration/ integrations/ api/ app.py config.py tests/ (not tests/ui/) pyproject requirements .github/` and the planning docs PRD/architecture/rules/phases. **Person B (experience)** owns `templates/ static/ branding.py FRONTEND.md docs/design.md tests/ui/`. Never edit the other person's files; message them instead.
- **`docs/contracts.md` is the only coupling.** Additive optional fields: tell the other person. Breaking changes need both people (this is a §10 contract change).
- `docs/memory.md`: each person edits only their own track section. `docs/phases.md`: status column only, one row at a time, rebase first.
- Never work the same `TASK-*` at the same time; branches `feat/TASK-NNN-brief`; rebase on `main` at least every few hours; `main` must always boot.

---

## 10. AI implementer boundaries

| Allowed within an approved ticket | Requires owner approval | Forbidden |
|---|---|---|
| Read docs/files; implement bounded code+tests for the ticket; run `ruff`/types/`pytest` locally; report evidence; propose changes with rationale. | Add/upgrade a dependency; change an API/step contract or the solver's result shape; change a security boundary or the budget mechanism; non-trivial seed-schema change; anything touching the Vercel production project or env vars. | Put secrets in code/docs/logs; **invent test/CI/deploy results**; fabricate agent output to cover a failure; bypass validation, the approval gate, or the budget cap; silently expand scope; use real client/customer/SSI data; claim merged/deployed without evidence. |

Use **Accept-Edits** mode (review each change), per the hackathon rule. No unattended full-auto edits on this machine.

---

## 11. Documentation update policy

| Change | Update |
|---|---|
| Product behavior/scope | `PRD.md` (preserve IDs) → ripple to downstream docs. |
| Architecture decision | `architecture.md`; add an ADR if significant. |
| UI behavior/tokens | `design.md`. |
| Coding/policy | this `rules.md`. |
| Tickets/dependencies/traceability | `phases.md`. |
| Verified implementation status | `memory.md` (evidence-based, at checkpoints — created only at implementation kickoff). |

Material changes to an approved decision require the change-control flow in `02_WORKFLOW_AND_GATES.md §10`.

---

## 12. Definition of Done (per ticket)

A ticket is **done** only when all hold and are reported honestly:
1. In-scope behavior + linked AC satisfied; linked **AT-\*** implemented and **observed** passing (or approved manual verification recorded).
2. `ruff` (lint+format), type check, and `pytest` run **green** — with the commands and output reported.
3. Security/error/failure implications for the change addressed (key hygiene, input validation, honest failure, budget).
4. Diff reviewed: no unrelated or unapproved changes; dependency direction intact.
5. Relevant docs + `memory.md` updated with evidence.
6. Owner review obtained where policy requires (contract/security/dependency changes).

A code draft produced without running these checks is labeled **`Draft / not verified`**, not done. Checks that could not run are reported as **`Not run`** with the reason.

---

### Consistency note
Rules reflect the actual chosen stack (FastAPI/Python, no DB, gateway-only models) and the Standard-tier risk. No rule contradicts the approved PRD/architecture/design; unknown exact tool configs are deferred to the Phase-0 scaffold ticket, not assumed.
