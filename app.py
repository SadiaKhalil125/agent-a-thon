import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

import branding

ROOT = Path(__file__).resolve().parent
INDEX_PATH = ROOT / "templates" / "index.html"


def render_index() -> str:
    html = INDEX_PATH.read_text(encoding="utf-8")
    return (
        html.replace("{{PAGE_TITLE}}", branding.PAGE_TITLE)
        .replace("{{PRODUCT_NAME}}", branding.PRODUCT_NAME)
        .replace("{{PRODUCT_SUBTITLE}}", branding.PRODUCT_SUBTITLE)
        .replace("{{HERO_TITLE}}", branding.HERO_TITLE)
        .replace("{{HERO_LEAD}}", branding.HERO_LEAD)
        .replace("{{FOOTER_TEXT}}", branding.FOOTER_TEXT)
        .replace("{{EVENT_PILL}}", branding.EVENT_PILL)
    )

if os.path.isfile(".env.local"):
    load_dotenv(".env.local")  # on Vercel, values come from project Environment Variables

REQUIRED_ENV = ("LITELLM_API_KEY", "LITELLM_BASE_URL", "LITELLM_MODEL")


def litellm_configured() -> bool:
    return all(os.environ.get(name) for name in REQUIRED_ENV)


app = FastAPI()


class ChatRequest(BaseModel):
    message: str


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "litellm_configured": litellm_configured(),
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not litellm_configured():
        return JSONResponse(
            {
                "error": (
                    "LiteLLM is not configured yet. When you receive your key, "
                    "copy .env.local.example to .env.local, fill in the three values, "
                    "and restart uvicorn."
                )
            },
            status_code=503,
        )
    try:
        client = OpenAI(
            api_key=os.environ["LITELLM_API_KEY"],
            base_url=os.environ["LITELLM_BASE_URL"],
        )
        completion = client.chat.completions.create(
            model=os.environ["LITELLM_MODEL"],
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": req.message},
            ],
        )
        return {"reply": completion.choices[0].message.content}
    except Exception as err:
        print(err)
        return JSONResponse(
            {"error": "The AI call failed. Check the logs."}, status_code=500
        )


@app.get("/", response_class=HTMLResponse)
def home():
    return render_index()


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")