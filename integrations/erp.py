"""Simulated ERP / finance system (invoices, recovery budget, purchase orders)."""

from __future__ import annotations

from typing import Any, ClassVar

from integrations.base import Connector, external_id
from integrations.manifest import AuthSpec, ConnectorSpec, Endpoint


class ErpConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        id="erp",
        category="ERP / Finance",
        tier=1,
        label="Invoices, budgets and purchase orders (simulated)",
        capabilities=("read",),
        auth=AuthSpec(
            mode="oauth2",
            scopes=("invoices.read", "budgets.read", "purchase_orders.read"),
            rateLimit="30/min",
        ),
        endpoints=(
            Endpoint(method="GET", path="/mock/erp/invoices", direction="read"),
            Endpoint(method="GET", path="/mock/erp/budgets/recovery", direction="read"),
            Endpoint(method="GET", path="/mock/erp/purchase-orders", direction="read"),
        ),
    )

    def invoices(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for invoice in self.twin.invoices:
            milestone = self.twin.milestone(invoice.milestoneId)
            out.append(
                {
                    "invoiceNumber": external_id(invoice),
                    "description": invoice.description,
                    "amount": invoice.amount,
                    "currency": invoice.currency,
                    "status": "pending_milestone_acceptance",
                    "milestone": {
                        "id": milestone.id,
                        "name": milestone.name,
                        "dueDay": milestone.dueDay,
                    },
                }
            )
        return out

    def recovery_budget(self) -> dict[str, Any]:
        budget = self.twin.budget
        return {
            "budgetId": "BUD-RECOVERY",
            "name": "Delivery recovery budget",
            "amount": budget.recoveryBudget,
            "currency": budget.currency,
            "committed": 0,
        }

    def purchase_orders(self) -> list[dict[str, Any]]:
        option = self.twin.contractor
        person = self.twin.person(option.personId)
        return [
            {
                "poNumber": f"PO-DRAFT-{external_id(person)}",
                "vendorName": person.name,
                "amount": option.fixedCost,
                "currency": option.currency,
                "status": "not_issued",
            }
        ]

    def record_count(self) -> int:
        return len(self.twin.invoices) + len(self.purchase_orders()) + 1

    def sample(self) -> dict[str, Any]:
        return self.invoices()[0]
