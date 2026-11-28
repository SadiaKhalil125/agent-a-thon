"""Simulated HRIS (employee directory and leave requests)."""

from __future__ import annotations

from typing import Any, ClassVar

from integrations.base import Connector, email_for, external_id
from integrations.manifest import AuthSpec, ConnectorSpec, Endpoint


class HrisConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        id="hris",
        category="HRIS",
        tier=1,
        label="People directory and leave (simulated)",
        capabilities=("read",),
        auth=AuthSpec(mode="oauth2", scopes=("employees.read", "leave.read"), rateLimit="60/min"),
        endpoints=(
            Endpoint(method="GET", path="/mock/hris/employees", direction="read"),
            Endpoint(method="GET", path="/mock/hris/leave-requests", direction="read"),
        ),
    )

    def employees(self) -> list[dict[str, Any]]:
        return [
            {
                "employeeId": external_id(person),
                "displayName": person.name,
                "jobTitle": person.role,
                "employmentType": "CONTRACTOR" if person.kind == "contractor" else "FTE",
                "skills": list(person.skills),
                "workEmail": email_for(person.name),
                "status": "active",
            }
            for person in self.twin.people
        ]

    def leave_requests(self) -> list[dict[str, Any]]:
        requests: list[dict[str, Any]] = []
        for preset in self.twin.presets:
            if preset.source.system != "hris":
                continue
            payload = preset.source.payload
            requests.append(
                {
                    "requestId": f"LV-{1001 + len(requests)}",
                    "employeeId": payload.get("employeeId"),
                    "leaveType": payload.get("leaveType"),
                    "startDay": payload.get("startDay"),
                    "endDay": payload.get("endDay"),
                    "approvedBy": payload.get("approvedBy"),
                    "status": "approved",
                }
            )
        return requests

    def record_count(self) -> int:
        return len(self.twin.people)

    def sample(self) -> dict[str, Any]:
        leave = self.leave_requests()
        return {"employee": self.employees()[0], "leaveRequest": leave[0] if leave else None}
