"""GET /dev: a single-page engine test console for Person A (not the product UI).

Serves one static HTML file that calls the public API. No model call, no data of its own.
Disabled (404) on Vercel unless DEV_CONSOLE=1, so it never ships by accident.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

import config
from api.errors import ApiError

router = APIRouter()

CONSOLE_PATH = Path(__file__).resolve().parent.parent / "devconsole" / "index.html"


DEMO_PATH = Path(__file__).resolve().parent.parent / "devconsole" / "demo.html"


def console_html() -> str:
    """The full engine test console (served at /dev)."""
    return CONSOLE_PATH.read_text(encoding="utf-8")


def demo_html() -> str:
    """The simple guided demo page. Served at `/` for now (see `app.home`) so it opens on Vercel."""
    return DEMO_PATH.read_text(encoding="utf-8")


@router.get("/dev", response_class=HTMLResponse, include_in_schema=False)
def dev_console() -> str:
    if not config.dev_console_enabled():
        raise ApiError(404, "ValidationError", "Not found.")
    return console_html()


__all__ = ["console_html", "demo_html", "router"]
