"""Rule-based relevance scorer.

Formula and component definitions from RESEARCH.md §5.
All sub-scores ∈ [0, 1]; final score = round(100 × weighted sum).
Country is a hard pre-filter handled by the caller, not scored here.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import NamedTuple

from app.scoring.weights import SCORE_WEIGHTS


# ── sub-scores ────────────────────────────────────────────────────────────────

def _cpv_pair_score(tender_code: str, profile_code: str) -> float:
    """Score one (tender CPV, profile CPV) pair by longest shared prefix."""
    shared = 0
    for tc, pc in zip(tender_code[:8], profile_code[:8]):
        if tc == pc:
            shared += 1
        else:
            break
    if shared >= 8:
        return 1.00
    if shared >= 4:
        return 0.70
    if shared >= 3:
        return 0.45
    if shared >= 2:
        return 0.25
    return 0.00


def score_cpv(tender_cpvs: list[str], profile_cpvs: list[str]) -> float:
    """C1: max pairwise CPV match score. 0.5 neutral when no profile CPVs."""
    if not profile_cpvs:
        return 0.5
    if not tender_cpvs:
        return 0.0
    return max(
        _cpv_pair_score(tc, pc)
        for tc in tender_cpvs
        for pc in profile_cpvs
    )


def score_keyword(title: str, description: str | None, keywords: list[str]) -> float:
    """C2: keyword hits in title (weight 1.0) and description (weight 0.6)."""
    if not keywords:
        return 0.5  # neutral — no profile keywords defined
    title_low = title.lower()
    desc_low = (description or "").lower()
    hits = 0.0
    for kw in keywords:
        kw_low = kw.lower().strip()
        if not kw_low:
            continue
        if kw_low in title_low:
            hits += 1.0
        elif kw_low in desc_low:
            hits += 0.6
    threshold = max(1, math.ceil(0.5 * len(keywords)))
    return min(1.0, hits / threshold)


def score_value(
    estimated_value_eur: float | None,
    value_min: float | None,
    value_max: float | None,
) -> float:
    """C3: value within the profile band (both in EUR)."""
    if value_min is None and value_max is None:
        return 0.5  # no range defined — neutral
    if estimated_value_eur is None:
        return 0.5  # missing value — neutral (common; don't punish)
    v = estimated_value_eur
    lo, hi = value_min, value_max
    # Helpers guard against division by zero (value_min=0, or a notice with value 0).
    def _below(val: float, bound: float) -> float:
        return max(0.0, val / bound) if bound > 0 else 0.0

    def _above(bound: float, val: float) -> float:
        return max(0.0, bound / val) if val > 0 else 0.0

    if lo is not None and hi is not None:
        if lo <= v <= hi:
            return 1.0
        return _below(v, lo) if v < lo else _above(hi, v)
    if lo is not None:
        return 1.0 if v >= lo else _below(v, lo)
    # hi only
    return 1.0 if v <= hi else _above(hi, v)


def score_deadline(deadline: datetime | None, min_days_to_bid: int) -> float:
    """C4: enough time left to bid."""
    if deadline is None:
        return 0.5  # no deadline (PIN/award notices) — neutral
    now = datetime.now(timezone.utc)
    # SQLite returns naive datetimes; treat them as UTC
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    d = (deadline - now).days
    if d < 0:
        return 0.0
    if d < min_days_to_bid:
        return 0.3 * (d / max(1, min_days_to_bid))
    if d <= 45:
        return 1.0
    return max(0.6, 1.0 - (d - 45) / 120)


def score_buyer(match_count: int | None) -> float:
    """C5: buyer repeat behaviour from BuyerCategoryStat.notice_count.

    match_count = total notices by this buyer in any target CPV division.
    None = buyer not resolved yet → neutral 0.5.
    """
    if match_count is None:
        return 0.5   # buyer_id not resolved → neutral
    if match_count == 0:
        return 0.0   # known buyer, no matching-CPV history
    if match_count <= 2:
        return 0.5   # occasional
    if match_count <= 5:
        return 0.8   # regular
    return 1.0       # frequent / framework-style repeat


# ── reason generation ─────────────────────────────────────────────────────────

def _cpv_reason(s: float, tender_cpvs: list[str], profile_cpvs: list[str]) -> str:
    if not profile_cpvs:
        return "– No CPV codes in profile"
    if s >= 1.0:
        return "✅ Exact CPV match"
    if s >= 0.70:
        return "✅ Close CPV match (class level, 4-digit)"
    if s >= 0.45:
        return "⚠️ Partial CPV match (group level, 3-digit)"
    if s > 0:
        return "⚠️ Broad CPV match (division level, 2-digit)"
    return "❌ No CPV overlap with your profile"


def _kw_reason(s: float, keywords: list[str]) -> str:
    if not keywords:
        return "– No keywords in profile"
    if s >= 1.0:
        return "✅ All profile keywords matched"
    if s >= 0.6:
        return "✅ Most keywords matched in title/description"
    if s > 0:
        return "⚠️ Some keywords matched"
    return "❌ No profile keywords found"


def _val_reason(s: float, v_min: float | None, v_max: float | None) -> str:
    if v_min is None and v_max is None:
        return "– No value range in profile"
    if s >= 1.0:
        return "✅ Value within your target range"
    if s >= 0.5:
        return "⚠️ Value slightly outside your range"
    if s == 0.5:
        return "– Value not disclosed"
    return "❌ Value well outside your target range"


def _ddl_reason(s: float, deadline: datetime | None, min_days: int) -> str:
    if deadline is None:
        return "– No submission deadline (PIN or award notice)"
    now = datetime.now(timezone.utc)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    d = (deadline - now).days
    if d < 0:
        return "❌ Deadline has passed"
    if d < min_days:
        return f"❌ Only {d} days left — less than your {min_days}d minimum"
    if d <= 45:
        return f"✅ {d} days to deadline — comfortable window"
    return f"⚠️ {d} days to deadline — early stage"


# ── main scorer ───────────────────────────────────────────────────────────────

class ScoreResult(NamedTuple):
    score: int          # 0-100
    reasons: list[str]
    breakdown: dict     # sub-scores for debugging


def compute_score(
    tender_cpvs: list[str],
    title: str,
    description: str | None,
    deadline: datetime | None,
    estimated_value_eur: float | None,
    buyer_name: str | None,
    profile_cpv_codes: list[str],
    profile_keywords: list[str],
    profile_value_min: float | None,
    profile_value_max: float | None,
    profile_min_days_to_bid: int = 7,
    buyer_match_count: int | None = None,  # from BuyerCategoryStat (Phase 5)
) -> ScoreResult:
    s_cpv = score_cpv(tender_cpvs, profile_cpv_codes)
    s_kw  = score_keyword(title, description, profile_keywords)
    s_val = score_value(estimated_value_eur, profile_value_min, profile_value_max)
    s_ddl = score_deadline(deadline, profile_min_days_to_bid)
    s_buy = score_buyer(buyer_match_count)

    w = SCORE_WEIGHTS
    raw = (w["cpv"] * s_cpv + w["keyword"] * s_kw + w["value"] * s_val
           + w["deadline"] * s_ddl + w["buyer"] * s_buy)
    final = round(100 * raw)

    reasons = [
        _cpv_reason(s_cpv, tender_cpvs, profile_cpv_codes),
        _kw_reason(s_kw, profile_keywords),
        _val_reason(s_val, profile_value_min, profile_value_max),
        _ddl_reason(s_ddl, deadline, profile_min_days_to_bid),
    ]

    breakdown = {
        "sCPV": round(s_cpv, 3), "sKW": round(s_kw, 3),
        "sVAL": round(s_val, 3), "sDDL": round(s_ddl, 3),
        "sBUY": round(s_buy, 3),
    }
    return ScoreResult(score=final, reasons=reasons, breakdown=breakdown)
