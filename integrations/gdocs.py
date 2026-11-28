"""Simulated Google Meet and Google Docs: meeting minutes as a Docs API `documents.get` response.

Everything is fabricated and built in-process from the company database (a real, completed
meeting: its title, date, account, attendees and notes). Only meetings listed in `REQUESTS` have a
"Decisions and action items" block that holds a client request; the others are plain minutes.
No network, no credentials, nothing stored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from datahub import db, event_twin
from datahub.event_twin import ClientRequest, EventError

DOC_ID = re.compile(r"^doc-mtg-(\d{1,6})$")


@dataclass(frozen=True)
class MinutesRequest:
    """A client request agreed in a meeting (fabricated for the demo)."""

    title: str
    days: int
    skill: str
    due_day: int  # working-day number in the company calendar
    amount: int


REQUESTS: dict[int, MinutesRequest] = {
    422: MinutesRequest("SSO audit-log export", 4, "security", 8, 7500),
}


def meeting_for_doc(doc_id: str) -> dict[str, Any]:
    match = DOC_ID.match(doc_id)
    rows = (
        db.query(
            "SELECT m.id, m.title, m.type, m.start_at, m.status, m.notes, m.account_id, "
            "a.name AS account, e.name AS owner FROM meetings m "
            "JOIN accounts a ON a.id = m.account_id JOIN employees e ON e.id = m.owner_id "
            "WHERE m.id = ?",
            (int(match.group(1)),),
        )
        if match
        else []
    )
    if not rows:
        raise LookupError(doc_id)
    return rows[0]


def _paragraph(text: str, style: str = "NORMAL_TEXT") -> dict[str, Any]:
    return {
        "paragraph": {
            "paragraphStyle": {"namedStyleType": style},
            "elements": [{"textRun": {"content": text + "\n"}}],
        }
    }


def minutes_document(doc_id: str) -> dict[str, Any]:
    """The Google Docs API shape (`documentId`, `title`, `body.content[].paragraph...`)."""
    meeting = meeting_for_doc(doc_id)
    attendees = [
        r["name"]
        for r in db.query(
            "SELECT e.name FROM meeting_attendees ma JOIN employees e ON e.id = ma.employee_id "
            "WHERE ma.meeting_id = ? ORDER BY e.name",
            (meeting["id"],),
        )
    ]
    lines = [
        _paragraph(f"Minutes: {meeting['title']}", "HEADING_1"),
        _paragraph(f"Date: {meeting['start_at'][:10]}   Account: {meeting['account']}"),
        _paragraph(f"Organizer: {meeting['owner']}"),
        _paragraph("Attendees: " + (", ".join(attendees) if attendees else "organizer only")),
        _paragraph("Discussion", "HEADING_2"),
        _paragraph(f"Summary: {meeting['notes'] or 'No notes were recorded.'}"),
    ]
    request = REQUESTS.get(meeting["id"])
    if request is not None:
        due = working_date(request.due_day)
        lines += [
            _paragraph("The client walked through the roadmap and agreed the next step."),
            _paragraph("Decisions and action items", "HEADING_2"),
            _paragraph(f"Client request: {request.title}"),
            _paragraph(f"Scope: {request.days} working days of {request.skill} work"),
            _paragraph(f"Needed by: {due.isoformat()}"),
            _paragraph(f"Quoted value: {request.amount:,} USD"),
        ]
    return {
        "documentId": doc_id,
        "title": f"Minutes: {meeting['title']}",
        "revisionId": "rev-simulated-1",
        "body": {"content": lines},
    }


def working_date(day: int) -> date:
    return event_twin.working_calendar()[day - 1]


def text_lines(document: dict[str, Any]) -> list[str]:
    """The document's paragraphs as plain lines (what a reader of the Doc sees)."""
    out: list[str] = []
    for item in document.get("body", {}).get("content", []):
        elements = item.get("paragraph", {}).get("elements", [])
        text = "".join(e.get("textRun", {}).get("content", "") for e in elements).strip()
        if text:
            out.append(text)
    return out


_FIELDS = (
    ("Client request", re.compile(r"^Client request:\s*(.{1,80})$")),
    ("Scope", re.compile(r"^Scope:\s*(\d{1,2}) working days? of ([a-z][a-z ]{0,38}) work$")),
    ("Needed by", re.compile(r"^Needed by:\s*(\d{4}-\d{2}-\d{2})$")),
    ("Quoted value", re.compile(r"^Quoted value:\s*([\d,]{1,9}) USD$")),
)


def request_from_minutes(lines: list[str], account_id: int) -> ClientRequest:
    """Read the client request out of the minutes. Missing parts are named, never guessed."""
    found: dict[str, re.Match[str]] = {}
    for line in lines:
        for name, pattern in _FIELDS:
            match = pattern.match(line)
            if match and name not in found:
                found[name] = match
    missing = [name for name, _ in _FIELDS if name not in found]
    if missing:
        raise EventError(
            "The minutes do not contain a complete client request (missing: "
            + ", ".join(missing)
            + "), so there is nothing to plan."
        )
    try:
        return ClientRequest(
            kind="demand",
            accountId=account_id,
            title=found["Client request"].group(1).strip(),
            skill=found["Scope"].group(2).strip(),
            days=int(found["Scope"].group(1)),
            dueDate=date.fromisoformat(found["Needed by"].group(1)),
            amount=int(found["Quoted value"].group(1).replace(",", "")),
        )
    except ValueError:
        raise EventError(
            "The client request in the minutes has values outside the range."
        ) from None


__all__ = [
    "REQUESTS",
    "MinutesRequest",
    "meeting_for_doc",
    "minutes_document",
    "request_from_minutes",
    "text_lines",
    "working_date",
]
