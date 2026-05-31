"""Shared helpers for the source mappers (OCDS / eForms)."""
from __future__ import annotations

from typing import Any


def json_safe(obj: Any) -> Any:
    """Recursively replace non-JSON-serialisable floats (Infinity, NaN) with None.

    Postgres rejects Infinity/NaN inside a JSON column (psycopg raises
    InvalidTextRepresentation). These values arise from json.loads parsing
    the literal tokens Infinity / -Infinity / NaN, which both source APIs can emit.
    SQLite tolerates them, so this is a production-only failure mode.
    """
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
        return None
    return obj
