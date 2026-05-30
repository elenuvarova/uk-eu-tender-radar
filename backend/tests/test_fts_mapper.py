"""Unit tests for the FTS OCDS mapper using the real fixture from spike."""
import json
from pathlib import Path

import pytest

from app.ingestion.cpv import build_cpv_rows, cpv_division, is_in_niche
from app.ingestion.fts import normalize_releases
from app.ingestion.normalize.enums import (
    OPEN, SELECTIVE, TENDER, AWARD, MODIFICATION,
    STATUS_OPEN, AWARDED, CANCELLED,
    map_notice_type, map_procedure_type, map_status,
)
from app.ingestion.normalize.ocds import normalize_fts_release

FIXTURE = Path(__file__).parent / "fixtures" / "fts_release_package.json"


@pytest.fixture(scope="module")
def raw_package():
    return json.loads(FIXTURE.read_text())


@pytest.fixture(scope="module")
def releases(raw_package):
    return raw_package.get("releases", [])


@pytest.fixture(scope="module")
def first_tender(releases):
    """First release that has a tender.title."""
    for r in releases:
        if (r.get("tender") or {}).get("title"):
            return r
    pytest.skip("No tender-stage release in fixture")


# ── mapper shape ──────────────────────────────────────────────────────────────

def test_fixture_loaded(releases):
    assert len(releases) > 0


def test_normalize_returns_required_keys(first_tender):
    row = normalize_fts_release(first_tender)
    required = {
        "id", "source", "source_notice_id", "source_url",
        "title", "title_lang", "notice_type", "procedure_type", "status",
        "publication_date", "raw_json", "_cpv_codes",
    }
    assert required <= set(row.keys())


def test_id_format(first_tender):
    row = normalize_fts_release(first_tender)
    assert row["id"].startswith("UK:")
    assert row["source"] == "UK"


def test_source_url_uses_notice_id(first_tender):
    row = normalize_fts_release(first_tender)
    assert row["source_notice_id"] in row["source_url"]
    assert "find-tender.service.gov.uk" in row["source_url"]


def test_buyer_name_resolved(first_tender):
    row = normalize_fts_release(first_tender)
    # Buyer name comes from parties[], not from the buyer ref
    assert row["buyer_name"] is not None and len(row["buyer_name"]) > 0


def test_buyer_country_normalized_to_iso(first_tender):
    row = normalize_fts_release(first_tender)
    # FTS returns "United Kingdom" as countryName — mapper normalizes to ISO "GB"
    assert row["buyer_country"] == "GB"


def test_publication_date_tz_aware(first_tender):
    from datetime import timezone
    row = normalize_fts_release(first_tender)
    assert row["publication_date"].tzinfo is not None
    assert row["publication_date"].tzinfo == timezone.utc


def test_cpv_codes_no_duplicates(first_tender):
    row = normalize_fts_release(first_tender)
    codes = row["_cpv_codes"]
    assert len(codes) == len(set(codes))


def test_title_lang_is_en(first_tender):
    row = normalize_fts_release(first_tender)
    assert row["title_lang"] == "en"


# ── enum mappers ──────────────────────────────────────────────────────────────

def test_map_procedure_type_open():
    assert map_procedure_type("open") == OPEN


def test_map_procedure_type_selective():
    assert map_procedure_type("selective") == SELECTIVE


def test_map_procedure_type_unknown():
    from app.ingestion.normalize.enums import PROC_OTHER
    assert map_procedure_type("unknown-value") == PROC_OTHER


def test_map_notice_type_tender():
    assert map_notice_type(["tender"]) == TENDER


def test_map_notice_type_award():
    assert map_notice_type(["award"]) == AWARD


def test_map_notice_type_update():
    assert map_notice_type(["tenderUpdate"]) == MODIFICATION


def test_map_status_active():
    assert map_status("active") == STATUS_OPEN


def test_map_status_complete():
    assert map_status("complete") == AWARDED


def test_map_status_cancelled():
    assert map_status("cancelled") == CANCELLED


# ── batch normalize ───────────────────────────────────────────────────────────

def test_normalize_releases_deduplicates(releases):
    # Pass the same releases twice; should dedup on id
    doubled = releases + releases
    rows = normalize_releases(doubled)
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))


def test_normalize_releases_count(releases):
    rows = normalize_releases(releases)
    assert len(rows) > 0
    assert len(rows) <= len(releases)


# ── CPV utilities ─────────────────────────────────────────────────────────────

def test_cpv_division():
    assert cpv_division("72500000") == "72"
    assert cpv_division("48000000") == "48"


def test_is_in_niche_tier1():
    assert is_in_niche(["72500000"])
    assert is_in_niche(["48000000"])


def test_is_in_niche_tier2():
    assert is_in_niche(["80420000"])  # e-learning
    assert is_in_niche(["79310000"])  # market research


def test_is_in_niche_false():
    assert not is_in_niche(["45000000"])  # construction
    assert not is_in_niche([])


def test_build_cpv_rows_dedup():
    rows = build_cpv_rows("UK:test", ["72500000", "72500000", "48000000"])
    codes = [r["cpv_code"] for r in rows]
    assert len(codes) == len(set(codes)) == 2


def test_build_cpv_rows_division():
    rows = build_cpv_rows("UK:test", ["72500000"])
    assert rows[0]["cpv_division"] == "72"
    assert rows[0]["tender_id"] == "UK:test"
