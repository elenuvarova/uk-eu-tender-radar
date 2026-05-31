"""EU TED v3 Search API ingestion client.

Anonymous access, ITERATION pagination (no cap), expert query language.
Confirmed field list and behaviour from SPIKE_FINDINGS.md.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Generator

import httpx

from app.ingestion.normalize.eforms import normalize_ted_notices

log = logging.getLogger(__name__)

TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"

# Fields confirmed to exist in the TED v3 API (spike + docs)
_FIELDS = [
    "publication-number",
    "notice-title",
    "buyer-name",
    "buyer-country",
    "classification-cpv",
    "total-value",
    "total-value-cur",
    "estimated-value-lot",
    "estimated-value-cur-lot",
    "notice-type",
    "form-type",
    "procedure-type",
    "place-of-performance",
    "deadline-receipt-tender-date-lot",
    "publication-date",
    "links",
    "winner-name",
]

# Countries to harvest (alpha-3 codes, EU + UK)
DEFAULT_COUNTRIES = [
    "GBR", "FRA", "DEU", "BEL", "NLD", "IRL",
    "ESP", "ITA", "POL", "AUT", "SWE", "DNK",
]

MAX_RETRIES = 4
RETRY_DELAYS = [5, 15, 30, 60]
MAX_PAGES = 200  # safety cap against runaway ITERATION cursors


def _post(client: httpx.Client, body: dict) -> dict:
    """POST with retry on 429/5xx."""
    for attempt, delay in enumerate(RETRY_DELAYS, 1):
        resp = client.post(TED_SEARCH_URL, json=body, timeout=60)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt < MAX_RETRIES:
                log.warning("TED %s (attempt %d), retrying in %ds", resp.status_code, attempt, delay)
                time.sleep(delay)
                continue
        resp.raise_for_status()
    raise RuntimeError("TED: exceeded retries")


def _build_query(
    since: datetime | None,
    countries: list[str] | None,
    cpv_divisions: list[str] | None,
    scope: str,
) -> str:
    """Build a TED expert query string."""
    parts: list[str] = []

    if since:
        parts.append(f"publication-date>={since.strftime('%Y%m%d')}")

    if countries:
        country_list = " ".join(countries)
        parts.append(f"buyer-country IN ({country_list})")

    if cpv_divisions:
        # TED expert query doesn't support prefix wildcards; use OR of division roots
        div_terms = " ".join(f"{d}000000" for d in cpv_divisions)
        parts.append(f"classification-cpv IN ({div_terms})")

    query = " AND ".join(parts) if parts else "*"
    return query + " SORT BY publication-date DESC"


def iter_notices(
    since: datetime | None = None,
    countries: list[str] | None = None,
    cpv_divisions: list[str] | None = None,
    scope: str = "ACTIVE",
    limit: int = 100,
) -> Generator[dict, None, None]:
    """
    Yield individual TED notice dicts using ITERATION pagination (no cap).
    `since` is a date; country/cpv_divisions pre-filter at the API level.
    """
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=1)
    if countries is None:
        countries = DEFAULT_COUNTRIES

    query = _build_query(since, countries, cpv_divisions, scope)
    log.info("TED query: %s", query)

    body: dict = {
        "query": query,
        "fields": _FIELDS,
        "page": 1,
        "limit": limit,
        "paginationMode": "ITERATION",
        "scope": scope,
        "onlyLatestVersions": True,
    }

    with httpx.Client() as client:
        pages_fetched = 0
        while True:
            if pages_fetched >= MAX_PAGES:
                log.warning("TED: hit MAX_PAGES=%d safety cap — truncating", MAX_PAGES)
                break
            data = _post(client, body)
            notices = data.get("notices") or []
            log.info("TED page %d: %d notices (total=%s)", pages_fetched + 1, len(notices), data.get("totalNoticeCount"))

            for n in notices:
                yield n

            pages_fetched += 1
            token = data.get("iterationNextToken")
            if not token or not notices:
                break
            body = {**body, "iterationNextToken": token}
            body.pop("page", None)  # token-based iteration ignores page


def fetch_and_normalize(
    since: datetime | None = None,
    countries: list[str] | None = None,
    cpv_divisions: list[str] | None = None,
    scope: str = "ACTIVE",
    limit: int = 100,
) -> list[dict]:
    """Convenience wrapper: fetch all notices and normalize them."""
    raw = list(iter_notices(since=since, countries=countries,
                             cpv_divisions=cpv_divisions, scope=scope, limit=limit))
    return normalize_ted_notices(raw)
