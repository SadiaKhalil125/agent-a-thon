import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field

import branding
import config
from api.devconsole import demo_html
from api.devconsole import router as devconsole_router
from api.errors import register_error_handlers
from api.execute import router as execute_router
from api.integrations import router as integrations_router
from api.run import router as run_router
from api.security import SecurityMiddleware, require_passcode
from api.state import router as state_router

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
register_error_handlers(app)
app.add_middleware(SecurityMiddleware)
app.include_router(state_router)
app.include_router(run_router)
app.include_router(execute_router)
app.include_router(integrations_router)
app.include_router(devconsole_router)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "llm_configured": config.llm_configured(),
        "passcodeRequired": config.demo_passcode() is not None,
    }


@app.post("/api/chat", deprecated=True, dependencies=[Depends(require_passcode)])
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
    # TEMPORARY (owner decision): a simple guided demo page is the home page so it opens on Vercel
    # (the full test console at /dev is hidden there). Person B: when the product UI is ready,
    # return render_index() here again and delete devconsole/, api/devconsole.py and
    # tests/test_devconsole.py.
    return demo_html()


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
