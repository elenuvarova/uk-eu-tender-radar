"""Unit tests for the TED eForms mapper using the real fixture from spike."""
import json
from pathlib import Path

import pytest

from app.ingestion.normalize.eforms import (
    _dedup_list,
    _extract_nuts,
    _extract_value,
    _map_form_type,
    _pick_lang,
    normalize_ted_notice,
    normalize_ted_notices,
)
from app.ingestion.normalize.enums import TENDER, AWARD, OPEN, STATUS_OPEN, AWARDED

FIXTURE = Path(__file__).parent / "fixtures" / "ted_search.json"


@pytest.fixture(scope="module")
def raw_response():
    return json.loads(FIXTURE.read_text())


@pytest.fixture(scope="module")
def notices(raw_response):
    return raw_response.get("notices", [])


@pytest.fixture(scope="module")
def competition_notice(notices):
    """First competition/cn-standard notice (has deadline)."""
    for n in notices:
        if n.get("form-type") == "competition":
            return n
    pytest.skip("No competition notice in fixture")


@pytest.fixture(scope="module")
def result_notice(notices):
    """First result/can-standard notice (no deadline)."""
    for n in notices:
        if n.get("form-type") == "result":
            return n
    pytest.skip("No result notice in fixture")


# ── helper functions ──────────────────────────────────────────────────────────

def test_dedup_list_removes_duplicates():
    assert _dedup_list(["A", "B", "A", "C", "B"]) == ["A", "B", "C"]


def test_dedup_list_empty():
    assert _dedup_list(None) == []
    assert _dedup_list([]) == []


def test_pick_lang_flat_map():
    # notice-title shape: {lang: str}
    field = {"eng": "English title", "fra": "Titre français"}
    assert _pick_lang(field) == "English title"


def test_pick_lang_array_map():
    # buyer-name shape: {lang: [str]}
    field = {"fra": ["Région Hauts-de-France"]}
    assert _pick_lang(field, preferred="eng") == "Région Hauts-de-France"


def test_pick_lang_prefers_eng():
    field = {"fra": "French", "eng": "English", "deu": "German"}
    assert _pick_lang(field) == "English"


def test_pick_lang_fallback_when_no_eng():
    field = {"fra": "Titre"}
    assert _pick_lang(field) == "Titre"


def test_extract_nuts_from_mixed_list():
    # place-of-performance contains NUTS + alpha-3 codes with dups
    places = ["FRE11", "FRA", "FRE11", "FRA"]
    assert _extract_nuts(places) == "FRE11"


def test_extract_nuts_de():
    assert _extract_nuts(["DEA33", "DEU", "DEA33", "DEU"]) == "DEA33"


def test_extract_nuts_no_nuts_codes():
    assert _extract_nuts(["FRA", "DEU"]) is None


def test_extract_value_from_estimated_lot():
    notice = {"estimated-value-lot": ["600000"], "estimated-value-cur-lot": ["EUR"]}
    val, cur = _extract_value(notice)
    assert val == 600000.0
    assert cur == "EUR"


def test_extract_value_from_total_value():
    notice = {"total-value": 1200000, "total-value-cur": ["EUR"]}
    val, cur = _extract_value(notice)
    assert val == 1200000.0
    assert cur == "EUR"


def test_extract_value_none():
    val, cur = _extract_value({})
    assert val is None
    assert cur is None


def test_map_form_type_competition():
    assert _map_form_type("competition", None) == TENDER


def test_map_form_type_result():
    assert _map_form_type("result", None) == AWARD


def test_map_form_type_can_fallback():
    assert _map_form_type(None, "can-standard") == AWARD


def test_map_form_type_cn_fallback():
    assert _map_form_type(None, "cn-standard") == TENDER


# ── normalize_ted_notice ──────────────────────────────────────────────────────

def test_normalize_competition_required_keys(competition_notice):
    row = normalize_ted_notice(competition_notice)
    required = {
        "id", "source", "source_notice_id", "source_url",
        "title", "title_lang", "notice_type", "procedure_type", "status",
        "publication_date", "raw_json", "_cpv_codes",
    }
    assert required <= set(row.keys())


def test_normalize_id_format(competition_notice):
    row = normalize_ted_notice(competition_notice)
    assert row["id"].startswith("EU:")
    assert row["source"] == "EU"


def test_normalize_source_url(competition_notice):
    row = normalize_ted_notice(competition_notice)
    pub_num = competition_notice["publication-number"]
    assert pub_num in row["source_url"]
    assert "ted.europa.eu" in row["source_url"]
    assert row["source_url"].endswith("/html")


def test_normalize_title_is_english(competition_notice):
    row = normalize_ted_notice(competition_notice)
    # Title must not be empty
    assert row["title"] and row["title"] != "(no title)"
    # If eng key present, title should come from it
    title_field = competition_notice.get("notice-title", {})
    if "eng" in title_field:
        assert title_field["eng"] in row["title"] or row["title"] in title_field["eng"]


def test_normalize_buyer_name_resolved(competition_notice):
    row = normalize_ted_notice(competition_notice)
    # buyer-name is lang->[str]; should resolve to a non-empty string
    assert row["buyer_name"] is not None and len(row["buyer_name"]) > 0


def test_normalize_buyer_country_alpha2(competition_notice):
    row = normalize_ted_notice(competition_notice)
    # All countries in fixture are 2-char ISO after normalization
    country = row["buyer_country"]
    if country:
        assert len(country) == 2, f"Expected alpha-2 country, got: {country}"


def test_normalize_cpv_deduped(competition_notice):
    row = normalize_ted_notice(competition_notice)
    codes = row["_cpv_codes"]
    assert len(codes) == len(set(codes)), "CPV codes should be deduplicated"


def test_normalize_notice_type_competition(competition_notice):
    row = normalize_ted_notice(competition_notice)
    assert row["notice_type"] == TENDER


def test_normalize_procedure_type_open(competition_notice):
    row = normalize_ted_notice(competition_notice)
    assert row["procedure_type"] == OPEN


def test_normalize_deadline_present_on_competition(competition_notice):
    row = normalize_ted_notice(competition_notice)
    assert row["deadline"] is not None


def test_normalize_deadline_tz_aware(competition_notice):
    row = normalize_ted_notice(competition_notice)
    if row["deadline"]:
        assert row["deadline"].tzinfo is not None


def test_normalize_deadline_offset_captured(competition_notice):
    row = normalize_ted_notice(competition_notice)
    if row["deadline_tz_offset"]:
        assert re.match(r"^[+-]\d{2}:\d{2}$", row["deadline_tz_offset"])


def test_normalize_deadline_none_on_result(result_notice):
    row = normalize_ted_notice(result_notice)
    # Result notices have no submission deadline (confirmed in spike)
    assert row["deadline"] is None


def test_normalize_notice_type_result(result_notice):
    row = normalize_ted_notice(result_notice)
    assert row["notice_type"] == AWARD


def test_normalize_region_is_nuts(competition_notice):
    row = normalize_ted_notice(competition_notice)
    # NUTS code if place-of-performance present; may be None for some notices
    if row["buyer_region_code"]:
        import re
        # NUTS: 2-letter country + alphanumeric suffix longer than 3 chars (e.g. FRE11, DEA33)
        assert re.match(r"^[A-Z]{2}[A-Z0-9]+$", row["buyer_region_code"]) and len(row["buyer_region_code"]) > 3


def test_normalize_publication_date_tz_aware(competition_notice):
    from datetime import timezone
    row = normalize_ted_notice(competition_notice)
    assert row["publication_date"].tzinfo == timezone.utc


def test_normalize_eur_value_set(competition_notice):
    row = normalize_ted_notice(competition_notice)
    if row["estimated_value"] and row["currency"] == "EUR":
        assert row["estimated_value_eur"] == row["estimated_value"]


# ── batch normalize ───────────────────────────────────────────────────────────

def test_normalize_ted_notices_deduplicates(notices):
    doubled = notices + notices
    rows = normalize_ted_notices(doubled)
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))


def test_normalize_ted_notices_count(notices):
    rows = normalize_ted_notices(notices)
    assert 0 < len(rows) <= len(notices)


import re  # noqa: E402 (needed by test_normalize_deadline_offset_captured)
