import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

import branding
import config

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

app = FastAPI()


class ChatRequest(BaseModel):
    message: str


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "llm_configured": config.llm_configured(),
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not config.llm_configured():
        return JSONResponse(
            {
                "error": (
                    "LLM provider is not configured. Copy .env.local.example to .env.local "
                    "and set LLM_BASE_URL / LLM_API_KEY / LLM_MODEL, then restart uvicorn."
                )
            },
            status_code=503,
        )
    try:
        settings = config.get_llm_settings()
        client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
        completion = client.chat.completions.create(
            model=settings.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": req.message},
            ],
        )
        return {"reply": completion.choices[0].message.content}
    except Exception as err:
        print(err)
        return JSONResponse({"error": "The AI call failed. Check the logs."}, status_code=500)


@app.get("/", response_class=HTMLResponse)
def home():
    return render_index()


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
