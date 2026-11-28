"""Connector base class: a read-only, native-looking view over the twin."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from integrations.manifest import ConnectorSpec, Manifest
from twin.model import Twin

# Fixed on purpose: a clock here would make runs non-deterministic (NFR-REL-001).
SIMULATED_LAST_SYNC = "2026-11-28T09:00:00Z"


class RecordNotFoundError(KeyError):
    """The requested record does not exist in the fabricated data."""


def external_id(item: Any) -> str:
    """The id this record carries in its (simulated) system, falling back to the seed id."""
    source = getattr(item, "source", None)
    return str(source.externalId) if source is not None else str(item.id)


def email_for(name: str) -> str:
    """A fabricated address on the reserved example.com domain."""
    return name.split(" (")[0].lower().replace(" ", ".") + "@example.com"


class Connector(ABC):
    spec: ClassVar[ConnectorSpec]

    def __init__(self, twin: Twin) -> None:
        self.twin = twin

    @abstractmethod
    def record_count(self) -> int: ...

    @abstractmethod
    def sample(self) -> dict[str, Any]:
        """One representative payload in this system's native-looking schema."""

    def manifest(self) -> Manifest:
        return Manifest(
            **self.spec.model_dump(),
            lastSync=SIMULATED_LAST_SYNC,
            recordCount=self.record_count(),
        )


__all__ = [
    "SIMULATED_LAST_SYNC",
    "Connector",
    "RecordNotFoundError",
    "email_for",
    "external_id",
]
