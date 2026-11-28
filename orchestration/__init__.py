"""Orchestration: RunContext schema, step registry/sequence, and call budget.

Control logic only (the Orchestrator). Holds no state between requests
(NFR-REL-001); state is carried in the client RunContext.
"""
