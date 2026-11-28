"""Simulated enterprise connectors (ADR-005, TASK-024).

Everything here is in-process and read-only over the fabricated seed: no outbound network, no
credentials, no persistence, no model calls. Each connector exposes a vendor-neutral, native-looking
view of the twin and a manifest that always says `mode: "simulated"`.
"""
