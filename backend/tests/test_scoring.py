"""Unit tests for the relevance scoring engine (RESEARCH.md §5)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.scoring.relevance import (
    ScoreResult,
    compute_score,
    score_cpv,
    score_deadline,
    score_keyword,
    score_value,
)


def _score(**kwargs) -> ScoreResult:
    defaults = dict(
        tender_cpvs=[], title="Test", description=None,
        deadline=None, estimated_value_eur=None, buyer_name=None,
        profile_cpv_codes=[], profile_keywords=[],
        profile_value_min=None, profile_value_max=None,
        profile_min_days_to_bid=7,
    )
    defaults.update(kwargs)
    return compute_score(**defaults)


# ── C1 CPV ────────────────────────────────────────────────────────────────────

def test_cpv_exact_match():
    assert score_cpv(["72500000"], ["72500000"]) == 1.0


def test_cpv_class_match_4digit():
    # 4 shared digits needed: e.g. 72500000 vs 72500001 → shares "7250" → class = 0.70
    assert score_cpv(["72500000"], ["72500001"]) == pytest.approx(0.70)


def test_cpv_group_match_3digit():
    # 725xxxxx vs 726xxxxx → 2 shared, but 72 is only 2
    # 72500000 vs 72000000: '7','2' match then '5' vs '0' differ → 2 shared = division
    # Let's try 73100000 vs 73200000: '7','3' match then '1' vs '2' differ → 2 = division
    # For 3-digit: 72100000 vs 72200000 → '7','2' then '1' vs '2' → 2 shared = division
    # Actually: 72100000 vs 72100001 → 7 shared = class? No, let's try properly:
    # group = 3 shared digits: "725" vs "725" but different at 4th
    assert score_cpv(["72500000"], ["72590000"]) == pytest.approx(0.45)


def test_cpv_division_match():
    assert score_cpv(["72500000"], ["72000000"]) == pytest.approx(0.25)


def test_cpv_no_match():
    assert score_cpv(["72500000"], ["45000000"]) == 0.0


def test_cpv_empty_profile_neutral():
    assert score_cpv(["72500000"], []) == pytest.approx(0.5)


def test_cpv_empty_tender():
    assert score_cpv([], ["72000000"]) == 0.0


def test_cpv_takes_best_pair():
    # One matching pair should dominate
    assert score_cpv(["45000000", "72500000"], ["72000000"]) == pytest.approx(0.25)
    assert score_cpv(["72500000", "45000000"], ["72500000"]) == 1.0


# ── C2 Keyword ───────────────────────────────────────────────────────────────

def test_kw_title_hit():
    assert score_keyword("Cloud Migration Project", None, ["cloud"]) == pytest.approx(1.0)


def test_kw_description_hit():
    s = score_keyword("Some procurement", "cloud migration services", ["cloud"])
    assert 0 < s < 1.0  # description hit = 0.6, threshold = 1 → 0.6/1 = 0.6


def test_kw_no_match():
    assert score_keyword("Construction work", None, ["cloud"]) == 0.0


def test_kw_empty_keywords_neutral():
    assert score_keyword("Anything", None, []) == pytest.approx(0.5)


def test_kw_saturates_at_half():
    # 4 keywords, threshold = ceil(0.5*4) = 2; 2 title hits = min(1, 2/2) = 1.0
    kws = ["cloud", "migration", "data", "GDPR"]
    s = score_keyword("cloud migration cloud migration", None, kws)
    assert s == pytest.approx(1.0)


def test_kw_case_insensitive():
    assert score_keyword("Cloud Migration", None, ["CLOUD"]) == pytest.approx(1.0)


# ── C3 Value ─────────────────────────────────────────────────────────────────

def test_value_in_band():
    assert score_value(500_000, 200_000, 2_000_000) == pytest.approx(1.0)


def test_value_null_neutral():
    assert score_value(None, 200_000, 2_000_000) == pytest.approx(0.5)


def test_value_no_band_neutral():
    assert score_value(500_000, None, None) == pytest.approx(0.5)


def test_value_below_min():
    s = score_value(50_000, 200_000, 2_000_000)
    assert 0 < s < 1.0
    assert s == pytest.approx(50_000 / 200_000)


def test_value_above_max():
    s = score_value(5_000_000, 200_000, 2_000_000)
    assert 0 < s < 1.0
    assert s == pytest.approx(2_000_000 / 5_000_000)


# ── C4 Deadline ──────────────────────────────────────────────────────────────

def _dl(days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def test_deadline_null_neutral():
    assert score_deadline(None, 7) == pytest.approx(0.5)


def test_deadline_expired():
    assert score_deadline(_dl(-1), 7) == 0.0


def test_deadline_too_soon():
    # deadline < min_days → s = 0.3 * d/min; just assert it's in the right range
    s = score_deadline(_dl(3), 14)
    assert 0 <= s < 0.3  # clearly in the "too soon" band


def test_deadline_comfortable():
    assert score_deadline(_dl(21), 7) == pytest.approx(1.0)
    assert score_deadline(_dl(45), 7) == pytest.approx(1.0)


def test_deadline_far_out():
    s = score_deadline(_dl(90), 7)
    assert 0.6 <= s < 1.0


# ── full compute_score ────────────────────────────────────────────────────────

def test_full_score_returns_score_result():
    result = _score(
        tender_cpvs=["72500000"],
        title="Cloud Migration Services",
        description="data centre consolidation",
        deadline=_dl(21),
        estimated_value_eur=850_000,
        profile_cpv_codes=["72000000"],
        profile_keywords=["cloud", "migration"],
        profile_value_min=200_000,
        profile_value_max=2_000_000,
    )
    assert isinstance(result, ScoreResult)
    assert 0 <= result.score <= 100
    assert len(result.reasons) == 5


def test_full_score_range():
    result = _score(
        tender_cpvs=["72500000"], title="Cloud",
        profile_cpv_codes=["72000000"], profile_keywords=["cloud"],
        deadline=_dl(21), estimated_value_eur=500_000,
        profile_value_min=200_000, profile_value_max=2_000_000,
    )
    assert 30 <= result.score <= 100  # at least some score from CPV+kw+val+ddl


def test_perfect_score_near_100():
    result = _score(
        tender_cpvs=["72500000"], title="cloud migration",
        profile_cpv_codes=["72500000"], profile_keywords=["cloud"],
        deadline=_dl(21), estimated_value_eur=500_000,
        profile_value_min=200_000, profile_value_max=2_000_000,
    )
    assert result.score >= 80  # exact CPV + kw + val + ddl = high score


def test_score_no_profile_all_neutral():
    result = _score()
    # All neutral = 0.5 × sum_weights = 0.5 → score = 50
    assert result.score == 50


def test_breakdown_keys(tmp_path):
    result = _score(tender_cpvs=["72000000"], profile_cpv_codes=["72000000"])
    assert set(result.breakdown.keys()) == {"sCPV", "sKW", "sVAL", "sDDL", "sBUY"}


def test_reasons_contain_checkmarks():
    result = _score(
        tender_cpvs=["72500000"], title="cloud",
        profile_cpv_codes=["72500000"], profile_keywords=["cloud"],
        deadline=_dl(21), estimated_value_eur=500_000,
        profile_value_min=200_000, profile_value_max=2_000_000,
    )
    # At least CPV and keyword should show ✅
    assert any("✅" in r for r in result.reasons)
