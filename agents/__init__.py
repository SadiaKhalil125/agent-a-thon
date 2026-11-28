"""Agent roles as plain-Python prompt/parse units over the LiteLLM gateway.

Agents reason and narrate; they NEVER compute numbers (that is twin.solver).
One model call per step (ADR-003, rules.md).
"""
