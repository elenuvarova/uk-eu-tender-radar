"""CPV code utilities: niche filter and TenderCpv row builder."""
from __future__ import annotations

# Digital/edtech CPV include-list from RESEARCH.md §4.
# Tier 1: always include (strong digital signal)
_TIER1_DIVISIONS = {"48", "72"}

# Tier 2: include (market/social research, analytics, UX, e-learning, IT training)
_TIER2_PREFIXES = {
    "79310000", "79311300", "79315000", "79320000", "79330000", "79340000",
    "80420000", "80530000", "80533",   # 80533xxx prefix match
    "80300000",
}

# Tier 3: only when co-occurring with Tier 1 (handled by caller if needed)
_TIER3_PREFIXES = {"73100000", "73200000", "73300000", "79400000"}


def is_in_niche(cpv_codes: list[str]) -> bool:
    """Return True if any CPV code matches the digital/edtech include-list."""
    for code in cpv_codes:
        div = code[:2]
        if div in _TIER1_DIVISIONS:
            return True
        for prefix in _TIER2_PREFIXES:
            if code.startswith(prefix):
                return True
    return False


def cpv_division(code: str) -> str:
    """Return the 2-digit CPV division for a code."""
    return code[:2] if len(code) >= 2 else code


def build_cpv_rows(tender_id: str, cpv_codes: list[str]) -> list[dict]:
    """Build TenderCpv field dicts for a set of CPV codes."""
    seen: set[str] = set()
    rows = []
    for code in cpv_codes:
        if code in seen:
            continue
        seen.add(code)
        rows.append({
            "tender_id": tender_id,
            "cpv_code": code,
            "cpv_division": cpv_division(code),
        })
    return rows
