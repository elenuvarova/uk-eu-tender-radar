"""Datetime helpers shared across scoring and the API.

SQLite — and Postgres columns declared TIMESTAMP WITHOUT TIME ZONE — return
tz-naive datetimes. Everything in this app is UTC, so coerce naive values to
UTC in one place instead of re-patching it at every comparison site.
"""
from __future__ import annotations

from datetime import datetime, timezone


def ensure_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def days_until(deadline: datetime, now: datetime) -> float:
    """Fractional days from now to deadline (no truncation)."""
    return (ensure_utc(deadline) - now).total_seconds() / 86400.0
