"""Static FX conversion to EUR for estimated values.

Both the FTS (OCDS) and TED normalizers convert estimated values to a common
EUR figure so value scoring and value filters work across sources. Until a
daily FX job exists, rates are a hand-maintained snapshot. Unknown currencies
return (None, None) rather than a fabricated number, so the caller leaves
estimated_value_eur NULL (treated as neutral by the scorer).
"""
from __future__ import annotations

from datetime import datetime

# Snapshot rates: 1 unit of CURRENCY = N EUR. Updated 2026-05-31.
# Covers EUR plus every non-euro currency among the harvested countries
# (GB, SE, DK, PL) with a little headroom (NO, CH, CZ, HU, RO).
FX_RATE_DATE: datetime = datetime(2026, 5, 31)
_TO_EUR: dict[str, float] = {
    "EUR": 1.0,
    "GBP": 1.17,
    "SEK": 0.092,
    "DKK": 0.134,
    "PLN": 0.235,
    "NOK": 0.086,
    "CHF": 1.04,
    "CZK": 0.040,
    "HUF": 0.0025,
    "RON": 0.20,
    "BGN": 0.511,
}


def to_eur(value: float | None, currency: str | None) -> tuple[float | None, datetime | None]:
    """Convert a value to EUR using the static snapshot.

    Returns (eur_value, fx_rate_date). For an unknown currency or missing
    value, returns (None, None) so the caller stores NULL.
    """
    if value is None or not currency:
        return None, None
    rate = _TO_EUR.get(currency.upper())
    if rate is None:
        return None, None
    return round(value * rate, 2), FX_RATE_DATE
