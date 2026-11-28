# Deployment guide (SSI Agent-A-Thon 2026)

Based on the [official Vercel quickstart](https://ssi-ai-hackathon.vercel.app/guide). This repo uses **Python + FastAPI** (Steps P1–P5). GitHub and Vercel steps match the shared guide (Steps 6–9).

## Prerequisites

- Python 3.12+
- Git
- LLM gateway values. The app reads provider-neutral `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (legacy `LITELLM_*` also accepted) from the environment — any OpenAI-compatible gateway. For submission, use the organizer LiteLLM values.

## Local setup

```powershell
cd c:\Users\s.khalil\Documents\Agent-a-thon
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.local.example` to `.env.local` and fill in your three LiteLLM values (no quotes, no spaces around `=`).

Verify your key (Windows — use `curl.exe`):

```powershell
curl.exe <LITELLM_BASE_URL>/models -H "Authorization: Bearer <LITELLM_API_KEY>"
```

Run locally:

```powershell
uvicorn app:app --reload
```

Open http://localhost:8000 and click **Ask**.

If PowerShell blocks `.venv` activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## LangGraph / LangChain (optional)

Add to `requirements.txt` when needed:

```
langgraph
langchain-openai
```

Point the model at LiteLLM:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model=os.environ["LITELLM_MODEL"],
    base_url=os.environ["LITELLM_BASE_URL"],
    api_key=os.environ["LITELLM_API_KEY"],
)
```

## GitHub (one-time)

1. Create a **public** repo on GitHub (no README / .gitignore — this folder already has them).
2. Push:

```powershell
git init
git add .
git commit -m "First version"
git branch -M main
git remote add origin https://github.com/<your-username>/Agent-a-thon.git
git push -u origin main
```

Confirm `.env.local` is **not** on GitHub. Search the repo for `sk-` — it must find nothing.

## Vercel (one-time)

1. Sign up at [vercel.com](https://vercel.com/signup) → **Hobby** → **Continue with GitHub**.
2. **Add New → Project** → import this repository.
3. **Framework Preset** should be **FastAPI**. Root directory: `./`.
4. **Environment Variables** — add the same three keys as in `.env.local`:
   - `LLM_BASE_URL` (or legacy `LITELLM_BASE_URL`)
   - `LLM_API_KEY` (or legacy `LITELLM_API_KEY`)
   - `LLM_MODEL` (or legacy `LITELLM_MODEL`)
5. Click **Deploy**. Production URL: `https://<project-name>.vercel.app`.

After the first deploy, every `git push` to `main` redeploys automatically.

### Changing secrets

1. Vercel → **Settings → Environment Variables** → edit → save.
2. **Deployments** → ⋯ on latest → **Redeploy**.
3. Update `.env.local` locally and restart `uvicorn`.

## Submit

On the hackathon portal **Submit** page:

| Field | Value |
| --- | --- |
| GitHub repo URL | `https://github.com/<you>/Agent-a-thon` |
| Live Vercel URL | Short `https://<name>.vercel.app` (not a long deployment URL) |
| Summary | Up to 600 characters |

Pre-submit checklist:

- Live app works in a private/incognito window.
- Repo is public; no API keys in code or history.
- Latest Vercel deployment shows **Ready**.

## Python limits on Vercel (free)

| Limit | Implication |
| --- | --- |
| 5 min per request | Long agent loops → one step per request or parallelize |
| No state between requests | Use browser or DB for conversation state |
| 500 MB bundle | No PyTorch/TensorFlow; use LiteLLM for models |
| 4.5 MB request/response | Keep uploads small |

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ModuleNotFoundError` on Vercel | Add the package to **both** `requirements.txt` and `[project].dependencies` in `pyproject.toml` (Vercel reads `pyproject.toml` when it has a `[project]` table; `tests/test_dependency_sync.py` checks they match), push |
| Works locally, fails on Vercel | Match env vars in Vercel, then **Redeploy** |
| `401` / Authentication Error | Re-copy key from organizer email |
| `model not found` | Use a model name from `/models` |
| `504` timeout | Shorter chains or parallel agents |

Full table: [official guide — Troubleshooting](https://ssi-ai-hackathon.vercel.app/guide).

## Security

- Never commit `.env.local` or put keys in source.
- Call LiteLLM only from server routes (`app.py`), never from browser-only code with exposed keys.
- Do not share your personal LiteLLM key.