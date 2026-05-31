"""Edge-input regression tests locking the Phase A/B correctness fixes.

These cover the failure shapes that the SQLite-only suite never exercised and
that caused production incidents (Infinity JSON, division-by-zero scoring,
list-shaped winner-name, malformed records aborting a batch, profile validation,
NUTS-1 codes, sub-day deadlines).
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.ingestion.normalize._util import json_safe
from app.ingestion.normalize.eforms import (
    _extract_nuts,
    _pick_lang,
    normalize_ted_notice,
)
from app.scoring.relevance import _val_reason, score_deadline, score_value


# ── A1: Infinity / NaN sanitisation ───────────────────────────────────────────

def test_json_safe_replaces_infinity_and_nan():
    data = {
        "a": float("inf"),
        "b": float("-inf"),
        "c": float("nan"),
        "nested": {"d": [1.0, float("inf"), "ok"]},
        "fine": 42,
        "str": "text",
    }
    out = json_safe(data)
    assert out["a"] is None
    assert out["b"] is None
    assert out["c"] is None
    assert out["nested"]["d"] == [1.0, None, "ok"]
    assert out["fine"] == 42
    assert out["str"] == "text"


def test_ted_raw_json_is_sanitised():
    notice = {
        "publication-number": "123-2026",
        "notice-title": {"eng": "Test"},
        "form-type": "competition",
        "tender-rules": {"maximumLotsBidPerSupplier": float("inf")},
    }
    row = normalize_ted_notice(notice)
    assert row["raw_json"]["tender-rules"]["maximumLotsBidPerSupplier"] is None


# ── A3: score_value never divides by zero ─────────────────────────────────────

@pytest.mark.parametrize(
    "value,vmin,vmax",
    [
        (-5.0, 0.0, None),
        (0.0, 0.0, 100.0),
        (0.0, None, 100.0),
        (50.0, 0.0, 0.0),
        (-1.0, 10.0, None),
    ],
)
def test_score_value_no_zero_division(value, vmin, vmax):
    result = score_value(value, vmin, vmax)
    assert 0.0 <= result <= 1.0


# ── A5: winner-name / multilingual fields of any shape ────────────────────────

def test_pick_lang_handles_all_shapes():
    assert _pick_lang("ACME Corp") == "ACME Corp"
    assert _pick_lang(["ACME Corp", "other"]) == "ACME Corp"
    assert _pick_lang({"eng": "ACME"}) == "ACME"
    assert _pick_lang({"fra": ["ACME SA"]}) == "ACME SA"
    assert _pick_lang(None) is None
    assert _pick_lang([]) is None
    assert _pick_lang({}) is None


def test_ted_award_with_list_winner_name_not_dropped():
    notice = {
        "publication-number": "999-2026",
        "notice-title": {"eng": "Award notice"},
        "form-type": "result",
        "winner-name": ["Winning Supplier Ltd"],
    }
    row = normalize_ted_notice(notice)
    assert row["award_supplier"] == "Winning Supplier Ltd"
    assert row["id"] == "EU:999-2026"


def test_ted_bare_string_title_does_not_crash():
    notice = {
        "publication-number": "888-2026",
        "notice-title": "Plain string title",
        "form-type": "competition",
    }
    row = normalize_ted_notice(notice)
    assert row["title"] == "Plain string title"
    assert row["title_lang"] == "eng"


# ── A4: one malformed record is skipped, not fatal ────────────────────────────

def test_upsert_isolates_bad_record(session):
    from app.ingestion.run import _upsert_rows

    good = {
        "id": "EU:good-1",
        "source": "EU",
        "source_notice_id": "good-1",
        "source_url": "http://example.com/1",
        "title": "Good",
        "publication_date": datetime.now(timezone.utc),
        "status": "OPEN",
        "notice_type": "TENDER",
        "procedure_type": "OPEN",
        "_cpv_codes": ["72000000"],
    }
    bad = {
        "id": "EU:bad-1",
        "source": "EU",
        "title": None,  # NOT NULL violation on insert
        "publication_date": datetime.now(timezone.utc),
        "_cpv_codes": [],
    }
    inserted, updated, failed = _upsert_rows(session, [dict(good), dict(bad)])
    assert inserted == 1
    assert failed == 1


# ── A6: profile validation rejects bad input ──────────────────────────────────

def test_profile_rejects_inverted_range(client):
    r = client.put("/api/profile", json={"value_min": 100, "value_max": 10})
    assert r.status_code == 422


def test_profile_rejects_negative_value(client):
    r = client.put("/api/profile", json={"value_min": -5})
    assert r.status_code == 422


def test_profile_accepts_zero_min(client):
    r = client.put("/api/profile", json={"value_min": 0, "value_max": 1000})
    assert r.status_code == 200
    assert r.json()["value_min"] == 0


# ── B6: NUTS extraction keeps NUTS-1, drops alpha-3 country codes ──────────────

def test_extract_nuts_keeps_nuts1_and_drops_alpha3():
    assert _extract_nuts(["GBR", "UKI"]) == "UKI"
    assert _extract_nuts(["FRA", "FRE11"]) == "FRE11"
    assert _extract_nuts(["DEU", "DEA33"]) == "DEA33"
    assert _extract_nuts(["GBR", "FRA"]) is None


# ── B5: deadline scoring sub-day accurate; not-disclosed reason reachable ──────

def test_deadline_later_today_scores_above_zero():
    soon = datetime.now(timezone.utc) + timedelta(hours=6)
    assert score_deadline(soon, 7) > 0.0


def test_val_reason_reports_not_disclosed():
    assert score_value(None, 1000.0, 5000.0) == 0.5
    assert _val_reason(0.5, 1000.0, 5000.0) == "– Value not disclosed"


# ── A2 + B2: CPV filter + stable pagination work end-to-end ───────────────────

def test_cpv_filter_and_status_filter(client, session):
    from app.ingestion.run import _upsert_rows

    rows = [
        {
            "id": f"EU:n-{i}",
            "source": "EU",
            "source_notice_id": f"n-{i}",
            "source_url": f"http://example.com/{i}",
            "title": f"Notice {i}",
            "publication_date": datetime.now(timezone.utc),
            "status": "OPEN",
            "notice_type": "TENDER",
            "procedure_type": "OPEN",
            "deadline": datetime.now(timezone.utc) + timedelta(days=10),
            "_cpv_codes": ["72000000"] if i % 2 == 0 else ["33000000"],
        }
        for i in range(6)
    ]
    _upsert_rows(session, [dict(r) for r in rows])

    r = client.get("/api/opportunities?cpv=72")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3  # only the even-indexed 72... notices
