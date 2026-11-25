# SSI Agent-A-Thon 2026 — reference

Quick links, rules, rubric, ideas, and deadlines. Use this so you don’t re-paste portal URLs in chat.

---

## Next steps (your checklist)

1. **Watch your inbox** — personal **LiteLLM** key: `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `LITELLM_MODEL` → `.env.local` + Vercel env vars.
2. **GitHub + Vercel** — [setup guide](https://ssi-ai-hackathon.vercel.app/guide) (this repo: Python/FastAPI track, Steps P1–P5 + shared Steps 6–9).
3. **Pick an idea** — [use cases & must-haves](https://ssi-ai-hackathon.vercel.app/use-cases).
4. **Build to the rubric** — [rules & scoring](https://ssi-ai-hackathon.vercel.app/rules).
5. **Submit** — [submit form](https://ssi-ai-hackathon.vercel.app/submit) with **the same email** you registered with.

---

## Official URLs

| Topic | URL |
| --- | --- |
| Vercel / Git / LiteLLM / Python guide | https://ssi-ai-hackathon.vercel.app/guide |
| What to build + sample ideas | https://ssi-ai-hackathon.vercel.app/use-cases |
| Rules, rubric, tools | https://ssi-ai-hackathon.vercel.app/rules |
| Submit entry | https://ssi-ai-hackathon.vercel.app/submit |

---

## Deadlines (PKT)

| When | What |
| --- | --- |
| **Fri, Nov 27, 2026, 12:00 AM** | Submit form **opens** (build weekend kickoff). |
| **Mon, Nov 30, 2026, 2:00 PM** | Submit **closes** (deadline). |
| Before deadline | You may **resubmit** anytime; **latest submission** is what gets evaluated. |

Until kickoff: register, read guides, get GitHub/Vercel ready, prototype locally.

**Prize:** Top submissions receive an **iPad**.

---

## Four must-haves (every entry)

1. **Agentic AI** — Agents that **plan**, **use tools/APIs**, and **act on results** via your LiteLLM key — not a single static prompt. **Multi-agent** workflows (distinct roles handing work to each other) are **strongly encouraged** and score higher on Completeness.
2. **Public or made-up data only** — No client, customer, or internal SSI data (app is on a public URL).
3. **Live on Vercel** — Working public URL evaluators can use. **JS (Next.js)** or **Python (FastAPI/Flask)**. **Streamlit and Gradio do not run on Vercel.**
4. **Core flow first** — One agent path **end-to-end**, then more agents, tools, polish. **Show each agent’s steps in the UI** so evaluators can see orchestration.

---

## Sample ideas (starting points, not limits)

You can bring **any** idea that meets the must-haves; samples use the **same rubric**.

| Sample | Flow (short) |
| --- | --- |
| **Fact-Checking Agents** | Extract claims → researchers check public sources (e.g. Wikipedia, World Bank) → verifier resolves disagreements, returns verdicts + links. |
| **Prior-Art Scout** | Search patents/papers (PatentsView, OpenAlex, arXiv) → analyst ranks overlap → critic loops search with sharper terms until results stabilize. |
| **Skeptical Debate Partner** | For vs against agents research and argue → moderator scores rounds + final summary; user can challenge either side. |

**Stronger Completeness:** More real agent work — planning, tools, agents checking each other — and **visible steps** in the app.

---

## Evaluation rubric (5 criteria)

Evaluators open your **live URL** from the portal and score:

| # | Criterion | What they look for |
| --- | --- | --- |
| 1 | **Completeness** (incl. multi-agent orchestration) | Works end-to-end; orchestration visible and functional. |
| 2 | **Creativity & uniqueness** | Fresh, specific idea (not generic chatbot). |
| 3 | **Technical execution** | Clean build, sensible agents, **API key not in code**. |
| 4 | **Presentation & live product** | On Vercel, easy to demo. |
| 5 | **Business value** | Would someone at SSI or a client actually use it? |

---

## Rules & guardrails

| Rule | Detail |
| --- | --- |
| **Individual work** | One entry per person; your repo, your Vercel deploy. |
| **Data** | Public or fabricated only. |
| **API key** | Vercel env vars + `.env.local`; **never** commit to GitHub. |
| **Cursor / Claude Code** | Use **Accept Edits** mode, not unattended full auto (company laptops, real credentials nearby). |
| **Key hygiene** | Don’t share keys; each participant has their own; spend cap per key. |
| **Budget / abuse** | Public URL = anyone can hit your app; optional passcode is a good stretch goal. |

---

## Tools & platform

| Layer | Choice |
| --- | --- |
| **Build** | Cursor or Claude Code; Next.js **or** FastAPI/Flask (LangGraph / Vercel AI SDK optional). |
| **Models** | LiteLLM personal key from organizers (`openai` SDK → SSI gateway only). |
| **Deploy** | Vercel **Hobby** (free); auto-deploy on push to `main`. |

### Python on Vercel (free) — plan for

| Limit | Implication |
| --- | --- |
| 5 min / request | Long chains → parallelize or **one agent step per request**. |
| No state between requests | Store conversation/state in browser or DB, not only in memory. |
| ~500 MB bundle | Lite ML libs OK; no huge stacks (e.g. PyTorch on server). |
| 4.5 MB req/resp | Keep uploads small. |

---

## Submit — what to send

On [submit page](https://ssi-ai-hackathon.vercel.app/submit) (same registration email):

| Field | Notes |
| --- | --- |
| **GitHub repo URL** | Public; no secrets. |
| **Live Vercel URL** | Short **`*.vercel.app`** from **Domains** — not a long one-off deployment URL. |
| **Project summary** | ≤ **600 characters**: what you built, who it’s for, 1–3 standouts. |

### Before you hit submit

- [ ] Incognito test of main feature end-to-end.
- [ ] Repo public; search GitHub for `sk-` → nothing.
- [ ] Vercel latest deployment **Ready**.
- [ ] App stays deployed until winners are announced (evaluation over following weeks).

---

## LiteLLM setup (from guide)

| Var | Purpose |
| --- | --- |
| `LITELLM_BASE_URL` | Gateway URL (often ends with `/v1`) |
| `LITELLM_API_KEY` | Personal `sk-…` key |
| `LITELLM_MODEL` | Allowed model name (verify with `GET …/models`) |

Local: `.env.local`. Vercel: Settings → Environment Variables → redeploy after changes.

Windows test key:

```powershell
curl.exe <LITELLM_BASE_URL>/models -H "Authorization: Bearer <LITELLM_API_KEY>"
```

Server-only calls: FastAPI routes in `app.py` / future `app/api/*` — never expose key to the browser (`NEXT_PUBLIC_*` or client-side LiteLLM).

---

## This repo

| Path | Purpose |
| --- | --- |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Local run, GitHub, Vercel, troubleshooting |
| [FRONTEND.md](./FRONTEND.md) | UI tokens, components, dark theme |
| [branding.py](./branding.py) | Product name / hero (placeholder until idea is set) |
| [.env.local.example](./.env.local.example) | Env var template |

---

## Agent implementation patterns (from guide appendix)

- **Pipeline:** A → B → C (e.g. extract → research → verify).
- **Parallel:** `asyncio.gather` / `Promise.all`, then combine.
- **Critic loop:** Cap rounds; critic returns `APPROVED` or feedback → worker revises.
- **LangGraph (Python):** `ChatOpenAI` with `base_url` + `api_key` from env → same LiteLLM gateway.

Multi-agent bonus: return **`steps`** (or similar) in API JSON and **render in the UI** for evaluators.