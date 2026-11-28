"""Connector registry: which simulated systems exist, in display order."""

from __future__ import annotations

from integrations.base import Connector
from integrations.calendar import CalendarConnector
from integrations.crm import CrmConnector
from integrations.erp import ErpConnector
from integrations.hris import HrisConnector
from integrations.manifest import Manifest
from integrations.tracker import TrackerConnector
from twin.model import Twin

# Tier 1 (read adapters). Tier 2 action sinks arrive with TASK-026, tier 3 with TASK-028.
CONNECTOR_CLASSES: tuple[type[Connector], ...] = (
    HrisConnector,
    TrackerConnector,
    ErpConnector,
    CrmConnector,
    CalendarConnector,
)


def build_registry(twin: Twin) -> dict[str, Connector]:
    return {cls.spec.id: cls(twin) for cls in CONNECTOR_CLASSES}


def list_manifests(twin: Twin) -> list[Manifest]:
    return [connector.manifest() for connector in build_registry(twin).values()]


__all__ = ["CONNECTOR_CLASSES", "build_registry", "list_manifests"]
