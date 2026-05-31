"""Tests for the shared FX-to-EUR conversion used by both normalizers."""
from datetime import datetime

from app.ingestion.normalize.fx import FX_RATE_DATE, to_eur


def test_gbp_converts_with_rate_date():
    val, date = to_eur(1000.0, "GBP")
    assert val == 1170.0
    assert date == FX_RATE_DATE


def test_eur_is_identity():
    val, date = to_eur(1000.0, "EUR")
    assert val == 1000.0
    assert date == FX_RATE_DATE


def test_non_euro_currency_converts():
    # SEK is one of the harvested non-euro currencies (Sweden)
    val, date = to_eur(1000.0, "SEK")
    assert val == 92.0
    assert date == FX_RATE_DATE


def test_currency_case_insensitive():
    assert to_eur(100.0, "gbp")[0] == to_eur(100.0, "GBP")[0]


def test_unknown_currency_returns_none():
    # Unknown currency must NOT fabricate a value
    assert to_eur(1000.0, "USD") == (None, None)
    assert to_eur(1000.0, "JPY") == (None, None)


def test_missing_value_or_currency_returns_none():
    assert to_eur(None, "GBP") == (None, None)
    assert to_eur(1000.0, None) == (None, None)
    assert to_eur(None, None) == (None, None)


def test_rate_date_is_a_datetime():
    assert isinstance(FX_RATE_DATE, datetime)
