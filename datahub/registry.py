"""One list of data tools: the REST endpoints and the agents' tools are both built from it.

Each entry wraps a repository function. Argument names, types and descriptions come from the
function itself, so an endpoint and the matching agent tool can never drift apart.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, get_type_hints

from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from datahub.repo import calendar as calendar_repo
from datahub.repo import crm, engineering, finance, hr
from datahub.repo.common import BadArgumentError

MAX_STRING_ARG = 200

AREAS = ("crm", "engineering", "hr", "finance", "calendar")


@dataclass(frozen=True)
class DataTool:
    area: str
    name: str
    func: Callable[..., dict[str, Any]]

    @property
    def tool_name(self) -> str:
        return f"{self.area}_{self.name}"

    @property
    def description(self) -> str:
        return inspect.cleandoc(self.func.__doc__ or self.name)


def _entry(area: str, func: Callable[..., dict[str, Any]]) -> DataTool:
    return DataTool(area=area, name=func.__name__, func=func)


TOOLS: tuple[DataTool, ...] = (
    _entry("crm", crm.search_leads),
    _entry("crm", crm.count_leads),
    _entry("crm", crm.list_meetings),
    _entry("crm", crm.pipeline_summary),
    _entry("crm", crm.account_overview),
    _entry("engineering", engineering.list_projects),
    _entry("engineering", engineering.project_detail),
    _entry("engineering", engineering.search_tickets),
    _entry("engineering", engineering.workload),
    _entry("engineering", engineering.teams_overview),
    _entry("engineering", engineering.commitments),
    _entry("hr", hr.headcount),
    _entry("hr", hr.find_employees),
    _entry("hr", hr.leave_in_range),
    _entry("hr", hr.hiring_pipeline),
    _entry("finance", finance.invoices),
    _entry("finance", finance.receivables_summary),
    _entry("finance", finance.budget_vs_actual),
    _entry("finance", finance.revenue_by_month),
    _entry("finance", finance.expenses_summary),
    _entry("calendar", calendar_repo.availability),
    _entry("calendar", calendar_repo.company_overview),
)

_BY_NAME = {t.tool_name: t for t in TOOLS}


def get(tool_name: str) -> DataTool | None:
    return _BY_NAME.get(tool_name)


def by_area(area: str) -> list[DataTool]:
    return [t for t in TOOLS if t.area == area]


def args_model(tool: DataTool) -> type[BaseModel]:
    """A strict pydantic model for the tool's arguments, built from its signature."""
    hints = get_type_hints(tool.func)
    fields: dict[str, Any] = {}
    for pname, param in inspect.signature(tool.func).parameters.items():
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[pname] = (hints[pname], default)
    return create_model(f"{tool.tool_name}_args", __config__=ConfigDict(extra="forbid"), **fields)


def call(tool: DataTool, raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate raw (possibly string) arguments, then run the repository function."""
    try:
        parsed = args_model(tool).model_validate(dict(raw))
    except ValidationError:
        raise BadArgumentError("Unknown or invalid argument.") from None
    values = parsed.model_dump(exclude_unset=True)
    for key, value in values.items():
        if isinstance(value, str) and len(value) > MAX_STRING_ARG:
            raise BadArgumentError(f"Argument '{key}' is too long.")
    return tool.func(**values)


__all__ = ["AREAS", "TOOLS", "DataTool", "args_model", "by_area", "call", "get"]
