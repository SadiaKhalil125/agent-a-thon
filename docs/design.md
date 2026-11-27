# Design — CompanyTwin AI
Project: CompanyTwin AI (organizational digital twin)
Complexity: Standard
Status: Draft
Version: 0.1
Owner: Participant
Last updated: 2026-11-27
Based on: docs/PRD.md v0.1 (Approved), docs/architecture.md v0.1 (Approved)

> UI is in scope (FR-UI-001…003). This document extends the existing shell (Poppins type, `data-theme` light/dark, card/button/field primitives in `static/css/main.css`) rather than inventing a new system.

---

## 1. Design Intent

**Audience.** An SSI evaluator (busy, technical-ish, time-boxed) opening a public URL with **no briefing and no presenter**, plus managers as the notional end user.

**Product principles.**
1. **Show the work.** The agent trail is the hero; orchestration must be legible, not hidden (G2, FR-ORCH-003).
2. **Honest by construction.** Every number is visibly tagged as a **fact**, a **calculation**, or an **estimate/AI judgment** (NFR-USE-001). The UI never implies the model "knows" the outcome.
3. **One guided path.** A single scrollable flow carries the evaluator from company → disruption → investigation → plans → verdict → approval → outcome (FR-UI-001).
4. **Calm, dense, professional.** Operational-dashboard tone; no marketing gloss; information density without clutter.

**Usability goals.** First-time completion of Flow A unaided (AC-UI-001-01); the milestone→tasks→invoice chain discoverable by eye (AC-TWIN-002-01); re-run obvious (FR-UI-003).

---

## 2. Screens & Navigation (Information Architecture)

Single-page, **section-sequential** layout (one route `/`, progressive reveal), not a multi-page app — this matches the client-driven step loop in architecture §2.

```
/  (one page, sections revealed in order)
├─ Header                      brand · theme toggle · event pill            [existing]
├─ §1 Company State            initial twin overview + dependency chain     FR-TWIN-001/002/003
├─ §2 Disruption Control       preset picker · "Introduce disruption"       FR-EVENT-001/003
├─ §3 Agent Trail              ordered step cards (the hero)                FR-ORCH-003, FR-IMP
├─ §4 Recovery Plans           side-by-side comparison + verdict            FR-PLAN, FR-VER
├─ §5 Approval                 select + approve a plan                      FR-EXEC-001
├─ §6 Outcome                  applied state change + match/mismatch        FR-EXEC-002/003
└─ Footer + Reset/Re-run       reset to seed                               FR-UI-003, FR-EXEC-004
```

Navigation aids: a slim sticky **progress rail** (State → Disrupt → Investigate → Plan → Verify → Approve → Outcome) that highlights the current stage and lets the evaluator jump back; "Reset demo" always reachable.

| Screen/section | Maps to FR | Primary job |
|---|---|---|
| §1 Company State | FR-TWIN-001/002/003 | Make connected commitments understandable at a glance. |
| §2 Disruption | FR-EVENT-001/002/003 | Trigger a preset (and, P3, edit parameters). |
| §3 Agent Trail | FR-ORCH-002/003/004/005, FR-IMP-001…004 | Show each agent's role, evidence, output, status, in order. |
| §4 Plans | FR-PLAN-001…004, FR-VER-001/002/003 | Compare alternatives; show the verifier rejection + revision. |
| §5 Approval | FR-EXEC-001 | Human gate before any change. |
| §6 Outcome | FR-EXEC-002/003/004 | Apply + verify against the chosen plan. |

---

## 3. Design Tokens

Extends the existing palette; values below are the authoritative set. Light is default; dark via `data-theme="dark"`.

### Color — semantic roles

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#f6f7f9` | `#0e1116` | App background |
| `--surface` | `#ffffff` | `#171b22` | Cards, panels |
| `--surface-2` | `#f0f2f5` | `#1f242d` | Insets, table headers, step body |
| `--border` | `#e2e6ec` | `#2a303a` | Hairlines, card borders |
| `--text` | `#1b1f24` | `#e8ecf1` | Primary text |
| `--text-muted` | `#5b6572` | `#9aa6b4` | Secondary/meta |
| `--primary` | `#2f6df6` | `#5b8cff` | Brand, primary actions, active rail |
| `--primary-contrast` | `#ffffff` | `#0e1116` | Text on primary |
| `--success` | `#1f9d57` | `#3fcf7f` | On-time, match, verified |
| `--warning` | `#c77d0a` | `#e8a33d` | At-risk, estimate, late-but-recoverable |
| `--danger` | `#d23f3f` | `#ff6b6b` | Missed deadline, rejected, failed step |
| `--info` | `#5a67d8` | `#8b95f0` | Neutral agent/info accents |

**Status → meaning is fixed** (reused everywhere): success = meets commitment, warning = at risk / estimate, danger = misses commitment / rejected / failed.

### Fact-type accents (NFR-USE-001 — the honesty system)

| Token | Color basis | Label text |
|---|---|---|
| `--fact` | `--text-muted` outline | **Fact** (from seed) |
| `--calc` | `--info` | **Calculated** (solver) |
| `--estimate` | `--warning` | **Estimate / AI judgment** |

### Agent-role accents (distinguish steps, not status)

Muted left-border + icon tint per role, drawn from an `--info`→teal→violet range: Observer, Impact, HR, Finance, Sales, Planner, Verifier, Execution. Role color is decorative; it never overrides a status color.

### Typography — Poppins (already loaded)

| Token | Value | Use |
|---|---|---|
| `--font` | Poppins, system-ui fallback | All text |
| `--fs-display` | 28/36 600 | Hero / section H1 |
| `--fs-h2` | 20/28 600 | Section titles |
| `--fs-h3` | 16/22 600 | Card titles, role names |
| `--fs-body` | 14/22 400 | Body |
| `--fs-meta` | 12.5/18 500 | Meta, tags, evidence refs |
| `--fs-mono` | 13/20 (ui-monospace) | IDs, numbers in comparisons |

Numbers in the plan comparison use tabular/monospace alignment for scanability.

### Spacing, radii, layout

| Token | Value |
|---|---|
| `--space-1…6` | 4, 8, 12, 16, 24, 32 px |
| `--radius-sm/md/lg` | 6 / 10 / 14 px |
| `--shadow-card` | `0 1px 2px rgba(0,0,0,.06), 0 2px 8px rgba(0,0,0,.04)` (lighter in dark) |
| `--container` | max 1080px, centered, `--space-5` gutter |
| Focus ring | `0 0 0 3px color-mix(--primary 40%, transparent)` |

---

## 4. Core Components

| Component | Purpose | Variants / states |
|---|---|---|
| **Button** (existing `.btn`) | Actions | `--primary` (Introduce, Approve), `--secondary` (Reset), `--ghost` (jump links); disabled, loading ("Working…"). |
| **Card / Panel** (existing `.card`) | Section container | default, inset (`--surface-2`). |
| **EntityList / StateCard** | Show projects, people, milestones, invoices | compact rows with status chips; expandable. |
| **DependencyChain** | Visualize milestone → tasks → invoice | horizontal connector chips with arrows; highlight on hover/focus (AC-TWIN-002). |
| **PresetSelect** | Choose disruption | radio-card group; one selected; keyboard-navigable. |
| **StepCard** (agent) | One agent step | header: role icon + name + **StatusBadge**; body: **evidence used** (chips/refs), **output** (narrative), optional derived facts; left border = role accent. States below. |
| **StatusBadge** | Step/plan status | `pending` (muted), `running` (pulsing dot), `done` (success check), `failed` (danger), `rejected` (danger), `revised` (info). |
| **FactTag** | Honesty label on any value | `Fact` / `Calculated` / `Estimate` (the §3 accents). |
| **PlanCard + PlanCompareTable** | Alternatives side by side | columns = plans; rows = Project A completion, Project B completion, deadlines met/missed, incremental cost, budget fit; cells carry status color + FactTag; one card can show **Rejected** (verdict). |
| **VerdictPanel** | Verifier output | verdict (approved/rejected) + reason; links the rejected plan to its **revised** successor. |
| **ApprovalBar** | Select + approve | plan radio + primary "Approve & apply"; confirm micro-step; disabled until a plan is chosen. |
| **OutcomePanel** | Post-execution | expected vs actual, per-field deltas, overall **match/mismatch** banner. |
| **Alert / Toast** | Inline status | info (not configured), warning (budget low), danger (step failed); never a blocking modal. |
| **ProgressRail** | Stage nav | 7 stages; active/complete/upcoming; click to jump back. |
| **ThemeToggle** (existing) | Light/dark | unchanged. |

Reuse expectation: StepCard, StatusBadge, FactTag and PlanCard are the reused primitives; everything else composes them.

---

## 5. Interactions & States

| State | Where | Treatment |
|---|---|---|
| **Loading seed** | §1 | skeleton rows; no layout shift. |
| **Empty (no run yet)** | §3–§6 | sections show a quiet "Introduce a disruption to begin" placeholder; progress rail at stage 1. |
| **Step running** | §3 | StepCard `running` with pulsing dot + "Role is investigating…"; page auto-scrolls the new card into view (respects reduced motion). |
| **Step done** | §3 | card settles to `done`; evidence + output revealed. |
| **Step failed** (FR-ORCH-005) | §3 | `failed` badge, danger left border, message "This step could not complete (model unavailable). No result was generated." + **Retry step**; **no fabricated content**. |
| **Verifier rejects** (FR-VER-002) | §3/§4 | rejected plan gets a danger ribbon + reason; a `revised` StepCard follows, visually linked ("Revised after verifier objection"). |
| **No feasible plan** (FR-PLAN-004) | §4 | plans still shown; each names the **constraint it violates** via danger FactTag; no false all-green. |
| **Not configured** (LiteLLM) | global | top info Alert reusing the existing message; Introduce button disabled with tooltip. |
| **Budget exhausted** (NFR-OPS) | §3 | warning Alert "Run budget reached"; further steps disabled; Reset offered. |
| **Awaiting approval** | §5 | ApprovalBar active; nothing has changed yet (reinforce "no change until you approve"). |
| **Executing / outcome** | §6 | brief applying state → OutcomePanel with match/mismatch. |
| **Reset** | footer | confirm micro-prompt → restore seed, clear trail, rail to stage 1. |
| Hover/focus/disabled | all controls | visible focus ring (§3); disabled = reduced opacity + `aria-disabled`. |

---

## 6. Responsive Behavior

Desktop-first (evaluators are on laptops), degrade gracefully.

| Breakpoint | Layout |
|---|---|
| ≥ 960px | Centered 1080px column; PlanCompareTable shows all plans as columns; progress rail sticky on the left or top. |
| 600–959px (tablet) | Single column; plans become stacked PlanCards with a sticky compare header; rail collapses to a top strip. |
| < 600px (phone) | Full-width cards; plans stack; rail becomes a compact step counter ("3/7 Investigate"); tables reflow to label:value rows. |

No horizontal scrolling of content; the only overflow allowed is an intentional table scroll on very narrow screens with a shadow affordance.

---

## 7. Accessibility (target WCAG 2.1 AA where practical — NFR-USE-002)

- **Keyboard:** every control (preset radios, jump links, Approve, Retry, Reset, theme) operable and in logical tab order; visible focus ring on all.
- **Live regions:** the agent trail container is `aria-live="polite"` so each completed step is announced; failures announced too. (Existing reply region already uses `aria-live`.)
- **Semantics:** sections use landmarks/headings; StepCards are a list; StatusBadge/FactTag convey meaning with **text + icon**, never color alone.
- **Contrast:** token pairs chosen for ≥ 4.5:1 body / ≥ 3:1 large text in both themes; verify danger/warning on their surfaces.
- **Motion:** step auto-scroll and pulsing dots gated behind `prefers-reduced-motion`.
- **Forms:** all inputs labeled; errors associated via `aria-describedby`.

---

## 8. Forms & Validation

| Form/action | Rules | Errors / confirms |
|---|---|---|
| **Preset select** (§2) | exactly one required before Introduce enables. | inline hint if none chosen. |
| **Custom event params** (P3) | who ∈ people, days within project window; bounded. | inline field errors; server revalidates (NFR-SEC-002). |
| **Approve & apply** (§5) | a plan must be selected; this **changes state**, so a one-tap confirm ("Approve Plan B? This applies it to the twin.") precedes execution. | confirm micro-step, not a heavy modal; cancel returns. |
| **Reset** | confirm ("Reset to initial company state?"). | restores seed; irreversible for the current run only (no external effect). |

Server errors surface as inline danger Alerts with safe generic text; no stack traces.

---

## 9. Screen Specs (key layouts)

**§1 Company State.** Header row "Northstar Systems — current commitments". Three stat tiles (Active projects, Milestones at stake, Invoices gated). Below: a **DependencyChain** for the primary project — `Integration (4d) → QA (2d) → Milestone D6 → Invoice $8,000` — with people/availability chips; and compact EntityLists for people (skills, availability) and the recovery budget ($2,000) + contractor option ($1,500 from day 1). Copy states these are **fabricated** planning figures (FactTag `Fact`). Acceptance: AC-TWIN-001-01, AC-TWIN-002-01.

**§3 Agent Trail.** Vertical stack of StepCards in run order. Each: role icon + name, StatusBadge, "Evidence used" chips (e.g. `Task T-INT`, `Person: Backup`, `Milestone D6`), then the model's narrative, then any derived facts with FactTag `Calculated`. The Impact step enumerates the full chain (AC-IMP-001-01); the HR step shows the backup's Project B conflict (AC-IMP-002-01); Finance shows exposure vs budget (AC-IMP-003-01). Acceptance: AC-ORCH-003/004/005.

**§4 Recovery Plans.** PlanCompareTable, plans as columns (e.g. *Wait for original*, *Reassign backup*, *Use contractor*). Rows: Project A completion, Project B completion, deadlines met/missed (status-colored), incremental cost (+ budget fit), each cell FactTagged `Calculated`. A rejected plan carries a danger ribbon + VerdictPanel reason; its revised successor is linked. Acceptance: AC-PLAN-001…004, AC-VER-002/003.

**§5 Approval.** ApprovalBar under the table: plan radios + "Approve & apply"; helper text "Nothing changes until you approve." Acceptance: AC-EXEC-001-01.

**§6 Outcome.** OutcomePanel: a match/mismatch banner, then expected-vs-actual per field (completion days, deadlines, cost, invoice eligibility), with deltas. Reset/Re-run beneath. Acceptance: AC-EXEC-002/003/004.

---

## 10. Design QA

Before design sign-off and again before release:
- [ ] All status colors carry a text/icon label (color-blind safe).
- [ ] Every displayed number has a FactTag (`Fact`/`Calculated`/`Estimate`) — no bare unexplained figures (NFR-USE-001).
- [ ] Failed-step state shows **no fabricated content** (FR-ORCH-005) and offers Retry.
- [ ] Verifier rejection visibly links to the revised plan (FR-VER-002).
- [ ] "No change until approval" is unmistakable at §5 (FR-EXEC-001).
- [ ] Full Flow A completable by keyboard only; focus visible throughout.
- [ ] Contrast AA verified in light **and** dark.
- [ ] Reduced-motion honored for auto-scroll/pulse.
- [ ] Layout holds at 1080 / tablet / phone with no content clipping.
- [ ] No invented screens beyond PRD scope (no auth, settings, accounts).

---

### Consistency notes
Extends existing tokens/components; no conflict with architecture (single page drives the step loop) or PRD actors (single evaluator, no roles). The optional synthetic-permission demo (FR-SEC-003, P3) is **not** designed here — it would be added as a clearly-labeled concept panel only if pursued. No design decision introduces new PRD scope.
