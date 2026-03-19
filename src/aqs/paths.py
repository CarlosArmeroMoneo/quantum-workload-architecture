from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_schema_path() -> Path:
    return repo_root() / "benchmarks" / "warehouse" / "schema.sql"
