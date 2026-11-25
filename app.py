import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from openai import OpenAI
from pydantic import BaseModel

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


PAGE = """<!doctype html>
<html><body style="max-width:640px;margin:40px auto;font-family:sans-serif">
  <h1>Agent-a-thon</h1>
  <textarea id="q" rows="4" style="width:100%"></textarea>
  <button id="ask">Ask</button>
  <p id="reply" style="white-space:pre-wrap"></p>
  <script>
    document.getElementById("ask").onclick = async () => {
      const btn = document.getElementById("ask");
      btn.disabled = true; btn.textContent = "Thinking...";
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: document.getElementById("q").value }),
      });
      const data = await res.json();
      document.getElementById("reply").textContent = data.reply ?? data.error;
      btn.disabled = false; btn.textContent = "Ask";
    };
  </script>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE