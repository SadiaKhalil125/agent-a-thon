"""Connector manifest models: the shape of `GET /api/integrations` (docs/contracts.md section 3)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Endpoint(_Frozen):
    method: Literal["GET", "POST"]
    path: str
    direction: Literal["read", "write"]


class AuthSpec(_Frozen):
    mode: Literal["oauth2", "api_key", "webhook_hmac"]
    scopes: tuple[str, ...]
    rateLimit: str


class ConnectorSpec(_Frozen):
    """The static part of a manifest (everything except the live record count)."""

    id: str
    category: str
    tier: Literal[1, 2, 3]
    label: str
    capabilities: tuple[Literal["read", "write", "webhook", "artifact"], ...]
    auth: AuthSpec
    endpoints: tuple[Endpoint, ...]


class Manifest(ConnectorSpec):
    mode: Literal["simulated"] = "simulated"
    status: Literal["connected"] = "connected"
    lastSync: str
    recordCount: int


__all__ = ["AuthSpec", "ConnectorSpec", "Endpoint", "Manifest"]
