"""Simulated CRM (customer accounts and commitments)."""

from __future__ import annotations

from typing import Any, ClassVar

from integrations.base import Connector, RecordNotFoundError, external_id
from integrations.manifest import AuthSpec, ConnectorSpec, Endpoint
from twin.model import Commitment


class CrmConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        id="crm",
        category="CRM",
        tier=1,
        label="Accounts and customer commitments (simulated)",
        capabilities=("read",),
        auth=AuthSpec(
            mode="oauth2",
            scopes=("accounts.read", "commitments.read", "meetings.read"),
            rateLimit="60/min",
        ),
        endpoints=(
            Endpoint(method="GET", path="/mock/crm/accounts/{id}", direction="read"),
            Endpoint(method="GET", path="/mock/crm/commitments", direction="read"),
            Endpoint(method="GET", path="/mock/crm/meetings", direction="read"),
        ),
    )

    def meetings(self) -> list[dict[str, Any]]:
        """Client-meeting notes logged by Business Development (from CRM-sourced presets).

        Sales, HR and Finance read the same record; the payload says who it was shared with.
        """
        return [
            {**preset.source.payload, "status": "logged"}
            for preset in self.twin.presets
            if preset.source.system == "crm"
        ]

    def _commitment(self, commitment: Commitment) -> dict[str, Any]:
        milestone = self.twin.milestone(commitment.milestoneId)
        customer = self.twin.customer(commitment.customerId)
        return {
            "commitmentId": external_id(commitment),
            "accountId": external_id(customer),
            "description": commitment.description,
            "milestone": milestone.name,
            "dueDay": milestone.dueDay,
            "status": "open",
        }

    def commitments(self) -> list[dict[str, Any]]:
        return [self._commitment(c) for c in self.twin.commitments]

    def account(self, account_id: str) -> dict[str, Any]:
        for customer in self.twin.customers:
            if account_id in (external_id(customer), customer.id):
                return {
                    "accountId": external_id(customer),
                    "name": customer.name,
                    "commitments": [
                        self._commitment(c)
                        for c in self.twin.commitments
                        if c.customerId == customer.id
                    ],
                }
        raise RecordNotFoundError(account_id)

    def record_count(self) -> int:
        return len(self.twin.commitments)

    def sample(self) -> dict[str, Any]:
        return self.account(external_id(self.twin.customers[0]))
