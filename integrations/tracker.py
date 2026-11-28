"""Simulated issue tracker (issues and the current sprint)."""

from __future__ import annotations

from typing import Any, ClassVar

from integrations.base import Connector, RecordNotFoundError, external_id
from integrations.manifest import AuthSpec, ConnectorSpec, Endpoint
from twin.model import Task


class TrackerConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        id="tracker",
        category="Issue tracker",
        tier=1,
        label="Issues and sprints (simulated)",
        capabilities=("read",),
        auth=AuthSpec(mode="api_key", scopes=("issues.read", "sprints.read"), rateLimit="120/min"),
        endpoints=(
            Endpoint(method="GET", path="/mock/tracker/issues", direction="read"),
            Endpoint(method="GET", path="/mock/tracker/issues/{key}", direction="read"),
            Endpoint(method="GET", path="/mock/tracker/sprints/current", direction="read"),
        ),
    )

    def _issue(self, task: Task) -> dict[str, Any]:
        twin = self.twin
        project = twin.project(task.projectId)
        assignee = twin.person(task.defaultAssigneeId)
        depends = [external_id(twin.task(dep)) for dep in task.dependsOn]
        return {
            "key": external_id(task),
            "summary": task.name,
            "issueType": "Task",
            "status": "To Do",
            "labels": [task.type],
            "project": {"key": project.id, "name": project.name},
            "assignee": {"accountId": external_id(assignee), "displayName": assignee.name},
            "estimateDays": task.days,
            "dependsOn": depends,
        }

    def issues(self) -> list[dict[str, Any]]:
        return [self._issue(task) for task in self.twin.tasks]

    def issue(self, key: str) -> dict[str, Any]:
        for task in self.twin.tasks:
            if key in (external_id(task), task.id):
                return self._issue(task)
        raise RecordNotFoundError(key)

    def current_sprint(self) -> dict[str, Any]:
        twin = self.twin
        return {
            "id": "SPR-CURRENT",
            "name": "Current delivery sprint (fictional)",
            "state": "active",
            "startDay": 1,
            "endDay": max(m.dueDay for m in twin.milestones),
            "issues": [external_id(task) for task in twin.tasks],
        }

    def record_count(self) -> int:
        return len(self.twin.tasks)

    def sample(self) -> dict[str, Any]:
        return self.issues()[0]
