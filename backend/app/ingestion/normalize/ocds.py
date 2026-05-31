"""OCDS 1.1 release -> TenderOpportunity normalization.

Implements the mapper decisions from docs/SPIKE_FINDINGS.md:
- CPV from tender.classification (primary); tender.items[].classification (fallback)
- source_notice_id = release.id (e.g. "051000-2026")
- source_url constructed from release.id
- Buyer name/address from parties[role=buyer], not from the buyer ref directly
- All fields nullable; handle award-stage (tender.* often null)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.ingestion.normalize.enums import (
    map_notice_type,
    map_procedure_type,
    map_status,
)

FTS_BASE_URL = "https://www.find-tender.service.gov.uk/Notice"

# FTS returns full country names, not ISO codes — map the ones we'll see.
_COUNTRY_NAME_TO_ISO = {
    "united kingdom": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
}


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO-8601 date or datetime string to a tz-aware UTC datetime."""
    if not value:
        return None
    # Accept both date-only (YYYY-MM-DD) and full datetime strings.
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(value[:len(fmt) + 6], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _json_safe(obj: Any) -> Any:
    """Recursively replace non-JSON-serialisable floats (Infinity, NaN) with None."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and (obj != obj or obj == float("inf") or obj == float("-inf")):
        return None
    return obj


def _deadline_offset(value: str | None) -> str | None:
    """Extract the timezone offset string from an ISO datetime, e.g. '+01:00'."""
    if not value:
        return None
    m = re.search(r"([+-]\d{2}:\d{2})$", value)
    return m.group(1) if m else None


def _find_party(parties: list[dict], role: str) -> dict | None:
    """Return the first party that has role in its roles list."""
    for p in parties or []:
        if role in (p.get("roles") or []):
            return p
    return None


def _extract_cpv(tender: dict) -> list[str]:
    """
    Extract unique CPV codes from a tender block.
    Primary: tender.classification (scheme=CPV)
    Fallback: tender.items[].classification + additionalClassifications
    """
    codes: list[str] = []
    # Primary path (confirmed in spike: always present when CPVs available)
    cls = tender.get("classification") or {}
    if cls.get("scheme", "").upper() == "CPV" and cls.get("id"):
        codes.append(cls["id"])

    # Fallback: item-level classifications
    for item in tender.get("items") or []:
        item_cls = item.get("classification") or {}
        if item_cls.get("scheme", "").upper() == "CPV" and item_cls.get("id"):
            codes.append(item_cls["id"])
        for add_cls in item.get("additionalClassifications") or []:
            if add_cls.get("scheme", "").upper() == "CPV" and add_cls.get("id"):
                codes.append(add_cls["id"])

    # Deduplicate, preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def normalize_fts_release(release: dict) -> dict[str, Any]:
    """
    Map one OCDS 1.1 release from Find a Tender to the TenderOpportunity field dict.
    Returns a plain dict; caller creates the SQLModel instance.
    """
    tender = release.get("tender") or {}
    parties = release.get("parties") or []
    tags = release.get("tag") or []

    # Identity
    notice_id = release.get("id", "")          # e.g. "051000-2026"
    ocid = release.get("ocid", "")

    # Buyer: resolve via parties[], not the buyer ref
    buyer_party = _find_party(parties, "buyer")
    buyer_name: str | None = None
    buyer_country: str | None = None
    buyer_region_raw: str | None = None
    buyer_region_code: str | None = None
    if buyer_party:
        buyer_name = buyer_party.get("name")
        addr = buyer_party.get("address") or {}
        raw_country = addr.get("countryName") or ""
        buyer_country = _COUNTRY_NAME_TO_ISO.get(raw_country.lower(), raw_country) or None
        raw_region = addr.get("region")
        buyer_region_raw = raw_region
        # Keep ITL/NUTS codes as-is; free-text values stored in _raw only
        if raw_region and re.match(r"^[A-Z]{2,3}\d", raw_region):
            buyer_region_code = raw_region

    # CPV
    cpv_codes = _extract_cpv(tender)

    # Value
    value_block = tender.get("value") or {}
    estimated_value: float | None = None
    currency: str | None = None
    if value_block.get("amount") is not None:
        try:
            estimated_value = float(value_block["amount"])
        except (TypeError, ValueError):
            pass
        currency = value_block.get("currency")

    # Dates
    pub_date_raw = release.get("date") or release.get("publishedDate")
    deadline_raw = (tender.get("tenderPeriod") or {}).get("endDate")
    publication_date = _parse_dt(pub_date_raw) or datetime.now(timezone.utc)
    deadline = _parse_dt(deadline_raw)
    deadline_tz_offset = _deadline_offset(deadline_raw)

    # Enums
    notice_type = map_notice_type(tags)
    procedure_type = map_procedure_type(tender.get("procurementMethod"))
    status = map_status(tender.get("status"))

    # Award supplier (present only on award-tag releases)
    award_supplier: str | None = None
    for award in release.get("awards") or []:
        for sup in award.get("suppliers") or []:
            # Resolve supplier name via parties if needed
            sup_name = sup.get("name")
            if not sup_name:
                sup_party = _find_party(parties, "supplier")
                sup_name = (sup_party or {}).get("name")
            if sup_name:
                award_supplier = sup_name
                break
        if award_supplier:
            break

    return {
        "id": f"UK:{ocid}",
        "source": "UK",
        "source_notice_id": notice_id,
        "source_url": f"{FTS_BASE_URL}/{notice_id}",
        "title": tender.get("title") or "(no title)",
        "title_lang": "en",
        "description": tender.get("description"),
        "buyer_name": buyer_name,
        "buyer_country": buyer_country or "GB",  # FTS is always UK
        "buyer_region_raw": buyer_region_raw,
        "buyer_region_code": buyer_region_code,
        "estimated_value": estimated_value,
        "currency": currency,
        "estimated_value_eur": None,  # set by FX job later
        "fx_rate_date": None,
        "publication_date": publication_date,
        "deadline": deadline,
        "deadline_tz_offset": deadline_tz_offset,
        "notice_type": notice_type,
        "procedure_type": procedure_type,
        "procedure_type_raw": tender.get("procurementMethodDetails"),
        "status": status,
        "award_supplier": award_supplier,
        "raw_json": _json_safe(release),
        "_cpv_codes": cpv_codes,  # consumed by caller to build TenderCpv rows
    }
