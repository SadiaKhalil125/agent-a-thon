"""Typed, parameterised, read-only queries per department (ADR-006).

Each function returns plain dicts. Agents reach them as tools (`agents/chat_tools.py`) and people
reach the same functions through `/api/data/*`. Nothing here calls a model.
"""
