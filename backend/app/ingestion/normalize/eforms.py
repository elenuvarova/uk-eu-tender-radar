"""TED Search API field model -> TenderOpportunity normalization.

Uses the TED v3 Search API field names directly (not the OCDS-for-eForms
conversion step) — confirmed in SPIKE_FINDINGS.md as sufficient and simpler.

Key shape facts from the live spike:
- notice-title : lang -> str  (flat map, e.g. {"eng": "...", "fra": "..."})
- buyer-name   : lang -> [str] (array per lang — different shape from title!)
- classification-cpv : list of strings, WITH duplicates -> dedup on ingest
- place-of-performance : list mixing NUTS codes + alpha-3 country codes, WITH dups
- deadline-receipt-tender-date-lot : list or None (None on result/award notices)
- total-value / estimated-value-lot : may be None; carry currency alongside
- buyer-country : list of ISO alpha-3 (e.g. ["FRA"]) -> normalize to alpha-2
- publication-date : "YYYY-MM-DD+HH:MM" (carries offset)
- source_url : https://ted.europa.eu/en/notice/{publication-number}/html
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.ingestion.normalize._util import json_safe
from app.ingestion.normalize.fx import to_eur
from app.ingestion.normalize.enums import (
    AWARD, CONTRACT, MODIFICATION, NOTICE_OTHER, PLANNING, TENDER,
    map_procedure_type,
    STATUS_OPEN, AWARDED, PLANNED,
)

TED_BASE_URL = "https://ted.europa.eu/en/notice"

# TED alpha-3 -> ISO alpha-2 for the countries we cover
_ALPHA3_TO_ALPHA2: dict[str, str] = {
    "GBR": "GB", "FRA": "FR", "DEU": "DE", "BEL": "BE",
    "NLD": "NL", "IRL": "IE", "ESP": "ES", "ITA": "IT",
    "POL": "PL", "AUT": "AT", "SWE": "SE", "DNK": "DK",
    "FIN": "FI", "NOR": "NO", "CHE": "CH", "PRT": "PT",
    "CZE": "CZ", "HUN": "HU", "ROU": "RO", "SVK": "SK",
    "BGR": "BG", "HRV": "HR", "SVN": "SI", "LTU": "LT",
    "LVA": "LV", "EST": "EE", "CYP": "CY", "MLT": "MT",
    "LUX": "LU", "GRC": "GR",
}

# TED form-type -> unified notice_type
_FORM_TYPE_MAP = {
    "planning": PLANNING,
    "competition": TENDER,
    "result": AWARD,
    "modification": MODIFICATION,
    "contract": CONTRACT,
}

# TED procedure-type codes -> OCDS procurementMethod for reuse of existing mapper
_TED_PROCEDURE_TO_OCDS = {
    "open": "open",
    "restricted": "selective",
    "comp-dial": "selective",
    "comp-tend": "selective",
    "innovation": "selective",
    "neg-w-call": "selective",
    "neg-wo-call": "limited",
}


def _pick_lang(field: Any, preferred: str = "eng") -> str | None:
    """
    Extract a string from a TED field that may be multilingual or flat.
    TED is inconsistent across fields and notice versions, so handle every shape:
    - str                -> return as-is        (e.g. a bare winner-name)
    - [str, ...]         -> first non-empty element
    - {lang: str}        -> notice-title style
    - {lang: [str]}      -> buyer-name style (first element of the list)
    Fall back through all language keys if preferred is missing.
    """
    if not field:
        return None
    if isinstance(field, str):
        return field or None
    if isinstance(field, list):
        for v in field:
            if isinstance(v, str) and v:
                return v
        return None
    if isinstance(field, dict):
        for lang in [preferred, *field.keys()]:
            val = field.get(lang)
            if val is None:
                continue
            if isinstance(val, list):
                return val[0] if val else None
            if isinstance(val, str) and val:
                return val
    return None


def _dedup_list(items: list | None) -> list:
    """Remove duplicates from a list, preserving first-seen order."""
    if not items:
        return []
    seen: set = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


_ALPHA3_CODES = frozenset(_ALPHA3_TO_ALPHA2)


def _extract_nuts(place_of_performance: list | None) -> str | None:
    """
    From place-of-performance (mixed NUTS + alpha-3 country codes, possibly
    duplicated), return the first NUTS code.

    NUTS codes are a 2-letter country prefix + 1–3 alphanumeric chars
    (NUTS-1 = 3 chars e.g. UKI, NUTS-2 = 4 e.g. FRE1, NUTS-3 = 5 e.g. DEA33).
    Alpha-3 country codes (GBR, DEU, FRA) are also 3 letters and otherwise
    match, so exclude the known set explicitly instead of by length.
    """
    for item in _dedup_list(place_of_performance):
        if (
            item
            and len(item) >= 3
            and re.match(r"^[A-Z]{2}[A-Z0-9]+$", item)
            and item not in _ALPHA3_CODES
        ):
            return item
    return None


def _parse_ted_date(value: str | None) -> datetime | None:
    """Parse TED date strings — handles Z suffix, offset, and fractional seconds."""
    if not value:
        return None
    # Normalize Z to +00:00 so fromisoformat handles it uniformly
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    # Fallback: strip offset and try simple formats
    bare = re.sub(r"[+-]\d{2}:\d{2}$", "", normalized).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(bare, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _deadline_offset(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"([+-]\d{2}:\d{2})$", value)
    return m.group(1) if m else None


def _extract_value(notice: dict) -> tuple[float | None, str | None]:
    """
    Extract estimated value + currency.
    Prefer estimated-value-lot (list of strings) then total-value (number).
    Multi-lot: sum values sharing the first lot's currency.
    """
    evl = notice.get("estimated-value-lot")
    cur_l = notice.get("estimated-value-cur-lot")
    if evl:
        lots = evl if isinstance(evl, list) else [evl]
        curs = (cur_l if isinstance(cur_l, list) else [cur_l]) if cur_l else []
        dominant_cur = (curs[0] if curs else None) or "EUR"
        total = 0.0
        found = False
        for i, raw in enumerate(lots):
            lot_cur = curs[i] if i < len(curs) else dominant_cur
            if lot_cur == dominant_cur:
                try:
                    total += float(raw)
                    found = True
                except (TypeError, ValueError):
                    pass
        if found:
            return total, dominant_cur

    tv = notice.get("total-value")
    tc = notice.get("total-value-cur")
    if tv is not None:
        try:
            currency = (tc[0] if isinstance(tc, list) else tc) if tc else "EUR"
            return float(tv), currency
        except (TypeError, ValueError):
            pass

    return None, None


def _map_form_type(form_type: str | None, notice_type_raw: str | None) -> str:
    """Map TED form-type to unified notice_type."""
    mapped = _FORM_TYPE_MAP.get((form_type or "").lower())
    if mapped:
        return mapped
    # Fallback: can-* notice types are awards
    if (notice_type_raw or "").startswith("can-"):
        return AWARD
    if (notice_type_raw or "").startswith("cn-"):
        return TENDER
    if (notice_type_raw or "").startswith("pin-"):
        return PLANNING
    return NOTICE_OTHER


def _map_ted_status(form_type: str | None, deadline_raw: str | None) -> str:
    """Derive unified status from TED form-type.

    Note: competition notices are stored as OPEN even past their deadline —
    CLOSED is synthetic and evaluated at query time, not persisted here. So
    deadline_raw doesn't affect the stored status and everything else is OPEN.
    """
    ft = (form_type or "").lower()
    if ft == "result":
        return AWARDED
    if ft == "planning":
        return PLANNED
    return STATUS_OPEN


def normalize_ted_notice(notice: dict) -> dict[str, Any]:
    """
    Map one TED v3 Search API notice dict to a TenderOpportunity field dict.
    Returns a plain dict; caller creates the SQLModel instance.
    """
    pub_num = notice.get("publication-number", "")
    form_type = notice.get("form-type")
    notice_type_raw = notice.get("notice-type")

    # Title (flat lang->str, but may also arrive as a bare string)
    title_field = notice.get("notice-title") or {}
    title = _pick_lang(title_field) or "(no title)"
    if isinstance(title_field, dict) and title_field:
        title_lang = "eng" if title_field.get("eng") else (next(iter(title_field), None) or "eng")
    else:
        title_lang = "eng"

    # Buyer (lang->[str] map)
    buyer_name = _pick_lang(notice.get("buyer-name"))

    # Country: alpha-3 list -> alpha-2
    countries_raw = _dedup_list(notice.get("buyer-country"))
    buyer_country_alpha2: str | None = None
    if countries_raw:
        alpha3 = countries_raw[0]
        buyer_country_alpha2 = _ALPHA3_TO_ALPHA2.get(alpha3, alpha3)

    # Region: NUTS code from place-of-performance
    nuts = _extract_nuts(notice.get("place-of-performance"))

    # CPV: dedup the flattened list
    cpv_codes = _dedup_list(notice.get("classification-cpv") or [])

    # Value
    estimated_value, currency = _extract_value(notice)
    estimated_value_eur, fx_rate_date = to_eur(estimated_value, currency)

    # Dates
    pub_date_raw = notice.get("publication-date")
    publication_date = _parse_ted_date(pub_date_raw) or datetime.now(timezone.utc)

    # Deadline: only on competition notices; list, take first element
    deadline_list = notice.get("deadline-receipt-tender-date-lot")
    deadline_raw: str | None = None
    if deadline_list:
        deadline_raw = deadline_list[0] if isinstance(deadline_list, list) else deadline_list
    deadline = _parse_ted_date(deadline_raw)
    deadline_tz_offset = _deadline_offset(deadline_raw)

    # Enums
    notice_type = _map_form_type(form_type, notice_type_raw)

    # TED procedure-type -> OCDS method name -> unified enum
    ted_proc = (notice.get("procedure-type") or "").lower()
    ocds_method = _TED_PROCEDURE_TO_OCDS.get(ted_proc, ted_proc)
    procedure_type = map_procedure_type(ocds_method)
    procedure_type_raw = ted_proc or None

    status = _map_ted_status(form_type, deadline_raw)

    # Award supplier: TED exposes winner-name if present (str / list / lang-map)
    award_supplier: str | None = _pick_lang(notice.get("winner-name"))

    return {
        "id": f"EU:{pub_num}",
        "source": "EU",
        "source_notice_id": pub_num,
        "source_url": f"{TED_BASE_URL}/{pub_num}/html",
        "title": title,
        "title_lang": title_lang,
        "description": None,  # description-lot not requested in Phase 1 query; added in Phase 3
        "buyer_name": buyer_name,
        "buyer_country": buyer_country_alpha2,
        "buyer_region_raw": nuts,
        "buyer_region_code": nuts,  # NUTS codes are already structured
        "estimated_value": estimated_value,
        "currency": currency,
        "estimated_value_eur": estimated_value_eur,
        "fx_rate_date": fx_rate_date,
        "publication_date": publication_date,
        "deadline": deadline,
        "deadline_tz_offset": deadline_tz_offset,
        "notice_type": notice_type,
        "procedure_type": procedure_type,
        "procedure_type_raw": procedure_type_raw,
        "status": status,
        "award_supplier": award_supplier,
        "raw_json": json_safe(notice),
        "_cpv_codes": cpv_codes,
    }


def normalize_ted_notices(notices: list[dict]) -> list[dict]:
    """Normalize a list of raw TED notice dicts, deduplicating on id."""
    import logging
    log = logging.getLogger(__name__)

    result = []
    seen: set[str] = set()
    for notice in notices:
        try:
            row = normalize_ted_notice(notice)
        except Exception as exc:  # noqa: BLE001
            log.warning("TED normalize error (pubnum=%s): %s",
                        notice.get("publication-number"), exc)
            continue
        uid = row["id"]
        if uid in seen:
            continue
        seen.add(uid)
        result.append(row)
    return result
