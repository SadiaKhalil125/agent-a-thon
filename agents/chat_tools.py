"""Data tools the "Ask the company" agents may call (ADR-006).

Every tool is read-only. The named tools come from `datahub.registry` (the same functions the REST
endpoints expose); `run_sql` is the guarded SELECT escape hatch from `datahub.sqlguard`. Results
are wrapped in one envelope so the model, the stream and the citation check all see the same data.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from datahub import registry, sqlguard
from datahub.db import DatabaseMissingError
from datahub.repo.common import BadArgumentError

logger = logging.getLogger("companytwin.chat")

MAX_RESULT_CHARS = 12000  # what one tool result may add to the model's context
PREVIEW_ROWS = 3  # rows shown in the stream; the model sees the full (capped) result

RUN_SQL = "run_sql"
SPECIALIST_AREAS = ("crm", "engineering", "hr", "finance", "calendar")


class _SqlArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sql: str = Field(
        description=(
            "One SQLite SELECT (or WITH ... SELECT) over the documented tables. No comments, no "
            "semicolons inside, at most 200 rows. Use COUNT/SUM/GROUP BY for numbers."
        ),
    )


def build_tools(area: str) -> list[BaseTool]:
    """The tools for one specialist: its area's named tools plus `run_sql`."""
    tools: list[BaseTool] = []
    for entry in registry.by_area(area):
        tools.append(
            StructuredTool(
                name=entry.tool_name,
                description=entry.description,
                args_schema=registry.args_model(entry),
                func=lambda **_: "",  # execution is done by `execute`, never by LangChain
            )
        )
    tools.append(
        StructuredTool(
            name=RUN_SQL,
            description=(
                "Run one read-only SQL SELECT over the company database for questions the named "
                "tools do not cover (joins across areas, custom filters or groupings)."
            ),
            args_schema=_SqlArgs,
            func=lambda **_: "",
        )
    )
    return tools


def execute(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run one tool call; returns `{ok: true, ...result}` or `{ok: false, error}`."""
    try:
        if name == RUN_SQL:
            sql_args = _SqlArgs.model_validate(args)
            return {"ok": True, **sqlguard.run_select(sql_args.sql)}
        entry = registry.get(name)
        if entry is None:
            return {"ok": False, "error": f"Unknown tool '{name}'."}
        return {"ok": True, **registry.call(entry, args)}
    except (BadArgumentError, sqlguard.SqlRejectedError) as exc:
        return {"ok": False, "error": str(exc)}
    except ValueError:
        return {"ok": False, "error": "Unknown or invalid argument."}
    except DatabaseMissingError:
        return {"ok": False, "error": "The company data is not available."}
    except Exception as exc:
        logger.error("tool %s crashed: %s", name, type(exc).__name__)
        return {"ok": False, "error": "The tool failed."}


def model_text(envelope: dict[str, Any]) -> str:
    """JSON for the model, with rows trimmed (and `truncated` set) to fit `MAX_RESULT_CHARS`."""
    shown = dict(envelope)
    rows = list(shown.get("rows") or [])
    text = json.dumps(shown, default=str, separators=(",", ":"))
    if len(text) <= MAX_RESULT_CHARS:
        return text
    while rows and len(text) > MAX_RESULT_CHARS:
        rows = rows[: max(1, len(rows) // 2)] if len(rows) > 1 else []
        shown["rows"] = rows
        shown["truncated"] = True
        shown["shownRows"] = len(rows)
        text = json.dumps(shown, default=str, separators=(",", ":"))
    return text


def row_count(envelope: dict[str, Any]) -> int:
    return len(envelope.get("rows") or [])


def preview(envelope: dict[str, Any]) -> dict[str, Any]:
    """The small, safe view of a result that goes into the SSE `tool_result` event."""
    if not envelope.get("ok"):
        return {"ok": False, "error": envelope.get("error", "The tool failed.")}
    out: dict[str, Any] = {
        "ok": True,
        "rowCount": row_count(envelope),
        "preview": (envelope.get("rows") or [])[:PREVIEW_ROWS],
    }
    for key in ("total", "truncated", "columns"):
        if key in envelope:
            out[key] = envelope[key]
    return out


_NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")
_DATE = re.compile(r"\d{4}-\d{2}(?:-\d{2})?(?:T\d{2}:\d{2})?")
_MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
_MONTH_DAY = re.compile(  # "25 Nov", "Dec 7": dates written out are not quantities
    rf"\b(?:\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTHS}|{_MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?)\b",
    re.IGNORECASE,
)
_YEAR = re.compile(r"\b20(?:2\d|3[0-5])\b")  # the company's years, not counts
_TIME = re.compile(r"(?<!\d)\d{1,2}:\d{2}(?!\d)")  # clock times like 10:30 are not quantities


def numbers_in(text: str) -> set[str]:
    """Numeric tokens in `text` (dates removed, commas stripped), as normalised strings."""
    cleaned = _YEAR.sub(" ", _MONTH_DAY.sub(" ", _TIME.sub(" ", _DATE.sub(" ", text))))
    found: set[str] = set()
    for match in _NUMBER.finditer(cleaned):
        token = match.group(0).replace(",", "")
        found.add(token)
        if "." in token:
            found.add(token.rstrip("0").rstrip("."))
    return found


__all__ = [
    "RUN_SQL",
    "SPECIALIST_AREAS",
    "build_tools",
    "execute",
    "model_text",
    "numbers_in",
    "preview",
    "row_count",
]
