"""Simulated calendar (free/busy and events)."""

from __future__ import annotations

from typing import Any, ClassVar

from integrations.base import Connector, RecordNotFoundError, email_for, external_id
from integrations.manifest import AuthSpec, ConnectorSpec, Endpoint
from twin.model import Person


class CalendarConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        id="calendar",
        category="Calendar",
        tier=1,
        label="Free/busy and events (simulated)",
        capabilities=("read",),
        auth=AuthSpec(mode="oauth2", scopes=("calendar.readonly",), rateLimit="100/min"),
        endpoints=(
            Endpoint(method="GET", path="/mock/calendar/freebusy", direction="read"),
            Endpoint(method="GET", path="/mock/calendar/events", direction="read"),
        ),
    )

    def _find_person(self, ref: str) -> Person:
        for person in self.twin.people:
            if ref in (person.id, external_id(person), email_for(person.name)):
                return person
        raise RecordNotFoundError(ref)

    def freebusy(self, person_ref: str, preset_id: str | None = None) -> dict[str, Any]:
        """Fixed bookings, plus the preset's disruption windows when a preset is given."""
        person = self._find_person(person_ref)
        busy: list[dict[str, Any]] = [
            {
                "startDay": a.startDay,
                "endDay": a.endDay,
                "reason": f"Booked: {self.twin.task(a.taskId).name}",
            }
            for a in self.twin.assignments
            if a.personId == person.id
        ]
        if preset_id is not None:
            try:
                preset = self.twin.preset(preset_id)
            except KeyError:
                raise RecordNotFoundError(preset_id) from None
            busy.extend(
                {"startDay": u.startDay, "endDay": u.endDay, "reason": "Out of office"}
                for u in preset.event.unavailable
                if u.personId == person.id
            )
        busy.sort(key=lambda b: (b["startDay"], b["endDay"]))
        return {
            "calendar": email_for(person.name),
            "owner": external_id(person),
            "availableWindows": [w.model_dump() for w in person.availability],
            "busy": busy,
        }

    def events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for preset in self.twin.presets:
            if preset.source.system != "calendar":
                continue
            payload = preset.source.payload
            events.append(
                {
                    "eventId": f"EV-{2001 + len(events)}",
                    "kind": "out_of_office",
                    "title": payload.get("title"),
                    "owner": payload.get("calendarOwner"),
                    "startDay": payload.get("startDay"),
                    "endDay": payload.get("endDay"),
                }
            )
        for assignment in self.twin.assignments:
            person = self.twin.person(assignment.personId)
            events.append(
                {
                    "eventId": f"EV-{2001 + len(events)}",
                    "kind": "booking",
                    "title": f"Booked: {self.twin.task(assignment.taskId).name}",
                    "owner": email_for(person.name),
                    "startDay": assignment.startDay,
                    "endDay": assignment.endDay,
                }
            )
        return events

    def record_count(self) -> int:
        return len(self.events())

    def sample(self) -> dict[str, Any]:
        return self.freebusy(self.twin.people[1].id)
