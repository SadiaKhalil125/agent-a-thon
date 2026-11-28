"""Runtime dependencies must be identical in pyproject.toml and requirements.txt.

Vercel installs from pyproject.toml when it has a [project] table, and pip/CI install from
requirements.txt. A drift between the two once left the deployed function without
`python-dotenv` (ModuleNotFoundError at import). This test makes the drift fail locally.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _requirements() -> set[str]:
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")}


def _pyproject() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return set(data["project"]["dependencies"])


def test_pyproject_dependencies_match_requirements() -> None:
    assert _pyproject() == _requirements()


def test_runtime_imports_are_declared() -> None:
    declared = " ".join(sorted(_pyproject()))
    for package in ("fastapi", "python-dotenv", "langgraph", "langchain-openai", "openai"):
        assert package in declared
