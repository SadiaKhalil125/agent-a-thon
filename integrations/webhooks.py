"""Simulated inbound webhooks: six systems from six departments, one inbox (docs/contracts.md 3b).

Each adapter knows one system's native payload. `sample()` builds a realistic payload from the
company database (real people, a real meeting, a real opportunity; only the event itself is made
up), and `normalize()` turns a received payload into the engine's event (a leave or a client
request) by code. No model is involved, nothing leaves the process, nothing is stored.

`sign`/`verify` are an HMAC-SHA256 over the exact request body, like most real providers: a body
that was changed after signing is refused.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import config
from datahub import db, event_twin
from datahub.event_twin import ClientRequest, EventError, LeaveEvent
from integrations import gdocs

SIGNATURE_HEADER = "X-Demo-Signature"
ABSENCE_EMOJI = {":palm_tree:", ":face_with_thermometer:", ":airplane:", ":baby:", ":no_entry:"}


class WebhookError(EventError):
    """The payload is not usable. The message is safe to show."""


@dataclass(frozen=True)
class Normalized:
    event: LeaveEvent | ClientRequest
    summary: str  # one plain sentence: what the system understood
    fetched: tuple[dict[str, str], ...] = field(default_factory=tuple)  # follow-up API calls made


@dataclass(frozen=True)
class Adapter:
    source: str
    system: str
    department: str
    event_type: str
    title: str
    description: str
    sample: Callable[[], dict[str, Any]]
    normalize: Callable[[dict[str, Any]], Normalized]


# ---- signing -----------------------------------------------------------------------------


def canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(config.webhook_secret(), body, hashlib.sha256).hexdigest()


def verify(body: bytes, header: str | None) -> bool:
    return hmac.compare_digest(sign(body).encode(), (header or "").encode())


# ---- helpers -----------------------------------------------------------------------------


def _employee(name: str) -> dict[str, Any]:
    rows = db.query(
        "SELECT e.id, e.name, e.email, e.role, m.email AS manager_email FROM employees e "
        "LEFT JOIN employees m ON m.id = e.manager_id WHERE e.name = ?",
        (name,),
    )
    if not rows:
        raise LookupError(name)
    return rows[0]


def _by_email(email: object) -> dict[str, Any]:
    if not isinstance(email, str) or not 3 <= len(email) <= 120:
        raise WebhookError("The payload has no usable employee email.")
    rows = db.query("SELECT id, name FROM employees WHERE lower(email) = lower(?)", (email,))
    if not rows:
        raise WebhookError("The payload names an employee who is not in the company records.")
    return rows[0]


def _day(value: object, what: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise WebhookError(f"The {what} is not a valid date.") from None


def _at(day_index: int) -> date:
    return event_twin.working_calendar()[day_index]


def _need(data: object, *path: str) -> Any:
    """Walk a nested dict; a missing key is a readable error, never a crash."""
    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise WebhookError(f"The payload is missing '{'.'.join(path)}'.")
        current = current[key]
    return current


def _leave(person_id: int, start: date, end: date, what: str) -> LeaveEvent:
    try:
        return event_twin.leave_between(person_id, start, end)
    except EventError as exc:
        raise WebhookError(f"{what}: {exc}") from None


# ---- 1. HR: time off approved (Workday-style) --------------------------------------------


def _hris_sample() -> dict[str, Any]:
    person = _employee("Marcus Lee")
    return {
        "eventType": "time_off.approved",
        "eventId": "evt-hr-20261201-0457",
        "occurredAt": f"{db.as_of().isoformat()}T08:12:00Z",
        "tenant": "northstar",
        "worker": {"email": person["email"], "displayName": person["name"]},
        "timeOff": {
            "category": "Sick",
            "firstDay": _at(1).isoformat(),
            "lastDay": _at(3).isoformat(),
            "approvedBy": person["manager_email"],
        },
    }


def _hris_normalize(payload: dict[str, Any]) -> Normalized:
    if _need(payload, "eventType") != "time_off.approved":
        raise WebhookError("This HR event is not an approved time-off request.")
    person = _by_email(_need(payload, "worker", "email"))
    first = _day(_need(payload, "timeOff", "firstDay"), "first day")
    last = _day(_need(payload, "timeOff", "lastDay"), "last day")
    kind = str(_need(payload, "timeOff", "category"))[:30]
    event = _leave(person["id"], first, last, "Time off")
    return Normalized(
        event, f"HR approved {kind.lower()} leave for {person['name']}, {first} to {last}."
    )


# ---- 2. Workspace/IT: Google Calendar out-of-office --------------------------------------


def _gcal_sample() -> dict[str, Any]:
    person = _employee("Quinn Okafor")
    return {
        "kind": "api#channel",
        "channelId": "chan-northstar-calendar-7",
        "resourceState": "exists",
        "changed": {
            "kind": "calendar#event",
            "eventType": "outOfOffice",
            "status": "confirmed",
            "summary": "Out of office",
            "creator": {"email": person["email"]},
            "start": {"date": _at(2).isoformat()},
            "end": {"date": (_at(6) + timedelta(days=1)).isoformat()},  # all-day end is exclusive
            "outOfOfficeProperties": {"autoDeclineMode": "declineAllConflictingInvitations"},
        },
    }


def _gcal_normalize(payload: dict[str, Any]) -> Normalized:
    changed = _need(payload, "changed")
    if _need(changed, "eventType") != "outOfOffice":
        raise WebhookError("This calendar change is not an out-of-office entry.")
    if _need(changed, "status") != "confirmed":
        raise WebhookError("The out-of-office entry is not confirmed.")
    person = _by_email(_need(changed, "creator", "email"))
    first = _day(_need(changed, "start", "date"), "start date")
    last = _day(_need(changed, "end", "date"), "end date") - timedelta(days=1)
    event = _leave(person["id"], first, last, "Out of office")
    return Normalized(
        event, f"{person['name']} put an out-of-office in Google Calendar, {first} to {last}."
    )


# ---- 3. Company-wide: Slack status change ------------------------------------------------


def _epoch(day: date, hour: int = 0) -> int:
    return int(datetime(day.year, day.month, day.day, hour, tzinfo=UTC).timestamp())


def _slack_sample() -> dict[str, Any]:
    person = _employee("Elena Varga")
    return {
        "type": "event_callback",
        "team_id": "T-NORTHSTAR",
        "event_id": "Ev-0457-NS",
        "event_time": _epoch(_at(0), 9),
        "event": {
            "type": "user_change",
            "user": {
                "id": "U-NS-0457",
                "real_name": person["name"],
                "profile": {
                    "email": person["email"],
                    "status_text": "Out sick, back next week",
                    "status_emoji": ":face_with_thermometer:",
                    "status_expiration": _epoch(_at(3) + timedelta(days=1)),  # clears after _at(3)
                },
            },
        },
    }


def _slack_normalize(payload: dict[str, Any]) -> Normalized:
    if _need(payload, "event", "type") != "user_change":
        raise WebhookError("This Slack event is not a profile change.")
    profile = _need(payload, "event", "user", "profile")
    if profile.get("status_emoji") not in ABSENCE_EMOJI:
        raise WebhookError("This Slack status does not announce an absence.")
    person = _by_email(_need(profile, "email"))
    sent, expires = _need(payload, "event_time"), _need(profile, "status_expiration")
    if (
        isinstance(sent, bool)
        or isinstance(expires, bool)
        or not isinstance(sent, int)
        or not isinstance(expires, int)
        or expires <= sent
    ):
        raise WebhookError("The Slack status has no usable expiry time.")
    first = datetime.fromtimestamp(sent, UTC).date()
    last = datetime.fromtimestamp(expires - 1, UTC).date()  # the status clears at `expires`
    event = _leave(person["id"], first, last, "Status")
    text = str(profile.get("status_text", ""))[:60]
    return Normalized(
        event,
        f"{person['name']} set the Slack status '{text}' until {last}: out {first} to {last}.",
    )


# ---- 4. Finance: travel booked -----------------------------------------------------------


def _travel_sample() -> dict[str, Any]:
    person = _employee("Pablo Schmidt")
    return {
        "event": "trip.booked",
        "bookingId": "TRP-20261201-31",
        "traveler": {"email": person["email"]},
        "trip": {
            "purpose": "Customer onsite visit",
            "destination": "Nairobi, KE",
            "departDate": _at(1).isoformat(),
            "returnDate": _at(3).isoformat(),
            "estimatedCostUsd": 1840,
            "financeApproved": True,
        },
    }


def _travel_normalize(payload: dict[str, Any]) -> Normalized:
    if _need(payload, "event") != "trip.booked":
        raise WebhookError("This travel event is not a booked trip.")
    if _need(payload, "trip", "financeApproved") is not True:
        raise WebhookError("The trip is not approved by Finance yet, so it is not planned for.")
    person = _by_email(_need(payload, "traveler", "email"))
    depart = _day(_need(payload, "trip", "departDate"), "departure date")
    back = _day(_need(payload, "trip", "returnDate"), "return date")
    event = _leave(person["id"], depart, back, "Trip")
    where = str(_need(payload, "trip", "destination"))[:40]
    return Normalized(
        event, f"Finance approved a trip to {where} for {person['name']}, {depart} to {back}."
    )


# ---- 5. Business Development: Google Meet transcript -> Google Docs minutes ---------------

MEETING_ID = 422  # a real, completed client meeting in the company database


def _meet_sample() -> dict[str, Any]:
    doc = f"doc-mtg-{MEETING_ID}"
    return {
        "subscription": "subscriptions/sub-northstar-meet-1",
        "eventType": "google.workspace.meet.transcript.v2.fileGenerated",
        "eventTime": f"{db.as_of().isoformat()}T11:20:00Z",
        "transcript": {
            "name": f"conferenceRecords/mtg-{MEETING_ID}/transcripts/t-1",
            "state": "FILE_GENERATED",
            "docsDestination": {
                "document": f"documents/{doc}",
                "exportUri": f"https://docs.google.com/document/d/{doc}/edit",
            },
        },
    }


def _meet_normalize(payload: dict[str, Any]) -> Normalized:
    if _need(payload, "eventType") != "google.workspace.meet.transcript.v2.fileGenerated":
        raise WebhookError("This Meet event is not a finished transcript.")
    if _need(payload, "transcript", "state") != "FILE_GENERATED":
        raise WebhookError("The transcript is not ready yet.")
    reference = str(_need(payload, "transcript", "docsDestination", "document"))
    doc_id = reference.removeprefix("documents/")
    try:  # the follow-up call a real receiver makes: Docs API documents.get
        meeting = gdocs.meeting_for_doc(doc_id)
        document = gdocs.minutes_document(doc_id)
    except LookupError:
        raise WebhookError("The minutes document could not be found.") from None
    lines = gdocs.text_lines(document)
    event = gdocs.request_from_minutes(lines, meeting["account_id"])
    fetched = (
        {
            "system": "Google Docs",
            "method": "GET",
            "path": f"/v1/documents/{doc_id}",
            "summary": f"Read '{document['title']}' ({len(lines)} lines of minutes).",
        },
    )
    return Normalized(
        event,
        f"The minutes of '{meeting['title']}' record a request from {meeting['account']}: "
        f"{event.title}, {event.days} working days, due {event.dueDate}, {event.amount:,} USD.",
        fetched,
    )


# ---- 6. Sales: CRM opportunity closed-won (Salesforce-style change event) ----------------


def _opportunity() -> dict[str, Any]:
    rows = db.query(
        "SELECT o.id, o.name, o.amount_usd, o.account_id, a.name AS account FROM opportunities o "
        "JOIN accounts a ON a.id = o.account_id WHERE o.stage = 'negotiation' "
        "AND o.amount_usd BETWEEN 15000 AND 40000 ORDER BY o.id LIMIT 1"
    )
    if not rows:
        raise LookupError("opportunity")
    return rows[0]


def _crm_sample() -> dict[str, Any]:
    opp = _opportunity()
    return {
        "channel": "/data/OpportunityChangeEvent",
        "data": {
            "payload": {
                "ChangeEventHeader": {
                    "entityName": "Opportunity",
                    "changeType": "UPDATE",
                    "changedFields": ["StageName"],
                    "recordIds": [f"OPP-{opp['id']}"],
                },
                "Name": f"{opp['account']} - platform delivery",
                "StageName": "Closed Won",
                "Amount": opp["amount_usd"],
                "AccountId": f"ACC-{opp['account_id']}",
                "Delivery_Days__c": 6,
                "Required_Skill__c": "kubernetes",
                "Requested_Go_Live__c": _at(8).isoformat(),
            },
            "event": {"replayId": 48213},
        },
    }


def _crm_normalize(payload: dict[str, Any]) -> Normalized:
    body = _need(payload, "data", "payload")
    header = _need(body, "ChangeEventHeader")
    if header.get("entityName") != "Opportunity" or _need(body, "StageName") != "Closed Won":
        raise WebhookError("This CRM change is not a deal that was just won.")
    account_ref = str(_need(body, "AccountId"))
    if not account_ref.startswith("ACC-") or not account_ref[4:].isdigit():
        raise WebhookError("The payload has no usable account id.")
    account_id = int(account_ref[4:])
    account = db.query("SELECT name FROM accounts WHERE id = ?", (account_id,))
    if not account:
        raise WebhookError("The payload names a client who is not in the company records.")
    amount, days = _need(body, "Amount"), _need(body, "Delivery_Days__c")
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise WebhookError("The deal amount is not a whole number.")
    if isinstance(days, bool) or not isinstance(days, int):
        raise WebhookError("The delivery days are not a whole number.")
    try:
        event = ClientRequest(
            kind="demand",
            accountId=account_id,
            title=str(_need(body, "Name"))[:80],
            skill=str(_need(body, "Required_Skill__c"))[:40],
            days=days,
            dueDate=_day(_need(body, "Requested_Go_Live__c"), "go-live date"),
            amount=amount,
        )
    except ValueError:
        raise WebhookError("The deal has values outside the range the planner covers.") from None
    return Normalized(
        event,
        f"The deal '{event.title}' with {account[0]['name']} was marked Closed Won "
        f"({event.amount:,} USD): {event.days} working days of work, go-live {event.dueDate}.",
    )


# ---- registry ----------------------------------------------------------------------------

ADAPTERS: tuple[Adapter, ...] = (
    Adapter(
        "hris",
        "HR system (Workday-style)",
        "Human Resources",
        "time_off.approved",
        "Sick leave approved",
        "HR approves sick leave. The people agent checks who can cover.",
        _hris_sample,
        _hris_normalize,
    ),
    Adapter(
        "gcal",
        "Google Calendar",
        "IT and Workspace",
        "calendar.event (outOfOffice)",
        "Out-of-office created",
        "A developer blocks a week in Google Calendar. No HR form was filed.",
        _gcal_sample,
        _gcal_normalize,
    ),
    Adapter(
        "slack",
        "Slack",
        "Company-wide",
        "user_change",
        "Sick status set in chat",
        "A status change in chat is often the first sign someone is out, before any form is filed.",
        _slack_sample,
        _slack_normalize,
    ),
    Adapter(
        "travel",
        "Travel and expenses",
        "Finance",
        "trip.booked",
        "Customer trip booked",
        "Finance approves a trip. The traveller is unavailable for delivery work.",
        _travel_sample,
        _travel_normalize,
    ),
    Adapter(
        "meet",
        "Google Meet + Google Docs",
        "Business Development",
        "meet.transcript.fileGenerated",
        "Client meeting minutes ready",
        "A client meeting ends. The system opens the minutes in Google Docs and finds a request.",
        _meet_sample,
        _meet_normalize,
    ),
    Adapter(
        "crm",
        "CRM (Salesforce-style)",
        "Sales",
        "OpportunityChangeEvent",
        "Deal closed-won",
        "Sales closes a deal. Can Engineering deliver what was sold, on the promised date?",
        _crm_sample,
        _crm_normalize,
    ),
)
BY_SOURCE: dict[str, Adapter] = {a.source: a for a in ADAPTERS}


def sample_envelope(adapter: Adapter) -> dict[str, Any]:
    """What the sending system would post: the exact body, its signature, and a tampered copy."""
    payload = adapter.sample()
    body = canonical(payload)
    return {
        "id": adapter.source,
        "source": adapter.source,
        "system": adapter.system,
        "department": adapter.department,
        "eventType": adapter.event_type,
        "title": adapter.title,
        "description": adapter.description,
        "payload": payload,
        "body": body,
        "signature": sign(body.encode()),
        "tamperedBody": canonical({**payload, "_edited_in_transit": True}),
    }


__all__ = [
    "ADAPTERS",
    "BY_SOURCE",
    "SIGNATURE_HEADER",
    "Adapter",
    "Normalized",
    "WebhookError",
    "canonical",
    "sample_envelope",
    "sign",
    "verify",
]
