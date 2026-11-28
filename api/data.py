"""GET /api/data/{area}/{tool}: read-only company data (ADR-006).

Thin REST view over the same repository functions the agents call. Nothing here writes, calls a
model or accepts SQL; arguments are validated, then bound as parameters inside the repository.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from api.errors import ApiError
from api.security import require_passcode
from datahub import dictionary, registry
from datahub.db import DatabaseMissingError
from datahub.repo.common import BadArgumentError

router = APIRouter(prefix="/api/data", dependencies=[Depends(require_passcode)])


@router.get("/tools")
def list_tools() -> dict[str, Any]:
    """Every data endpoint with its description and argument names."""
    return {
        "tools": [
            {
                "path": f"/api/data/{t.area}/{t.name}",
                "area": t.area,
                "name": t.tool_name,
                "description": t.description,
                "arguments": list(registry.args_model(t).model_fields),
            }
            for t in registry.TOOLS
        ]
    }


@router.get("/schema")
def get_schema(table: str | None = None) -> dict[str, Any]:
    """The data dictionary (overview and CREATE TABLE text)."""
    return {"tables": dictionary.table_names(), "schema": dictionary.describe_schema(table)}


@router.get("/{area}/{name}")
def call_tool(area: str, name: str, request: Request) -> dict[str, Any]:
    tool = registry.get(f"{area}_{name}")
    if tool is None:
        raise ApiError(404, "NotFound", "Unknown data endpoint.")
    try:
        return registry.call(tool, dict(request.query_params))
    except BadArgumentError as exc:
        raise ApiError(400, "ValidationError", str(exc)) from None
    except DatabaseMissingError:
        raise ApiError(503, "DataUnavailable", "The company data is not available.") from None


__all__ = ["router"]
