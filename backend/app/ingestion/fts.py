"""Find a Tender Service (FTS) OCDS ingestion client.

Fetches tender-stage release packages via cursor pagination and
normalizes each release into TenderOpportunity + TenderCpv rows.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Generator

import httpx

from app.ingestion.normalize.ocds import normalize_fts_release

log = logging.getLogger(__name__)

FTS_API = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
# Back-off config
MAX_RETRIES = 4
RETRY_DELAYS = [5, 15, 30, 60]  # seconds
MAX_PAGES = 200  # safety cap; ~20 000 releases per run


def _get(client: httpx.Client, url: str, params: dict | None = None) -> dict:
    """GET with exponential back-off on 429/5xx."""
    for attempt, delay in enumerate(RETRY_DELAYS, 1):
        resp = client.get(url, params=params, timeout=60)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt < MAX_RETRIES:
                log.warning("FTS %s (attempt %d), retrying in %ds", resp.status_code, attempt, delay)
                time.sleep(delay)
                continue
        resp.raise_for_status()
    raise RuntimeError("FTS: exceeded retries")


def iter_releases(
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
    stages: str = "tender",
    limit: int = 100,
) -> Generator[dict, None, None]:
    """
    Yield individual OCDS releases (not packages) from FTS.

    Follows links.next until exhausted. Dates must be full datetimes
    (FTS rejects date-only strings with 400).
    """
    if updated_from is None:
        updated_from = datetime.now(timezone.utc) - timedelta(days=7)
    if updated_to is None:
        updated_to = datetime.now(timezone.utc)

    params: dict = {
        "updatedFrom": updated_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updatedTo": updated_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stages": stages,
        "limit": limit,
    }

    headers = {
        "Accept": "application/json",
        "User-Agent": "tender-radar/0.1 (research project)",
    }

    with httpx.Client(headers=headers) as client:
        url = FTS_API
        page_params: dict | None = params
        pages_fetched = 0

        while url:
            if pages_fetched >= MAX_PAGES:
                log.warning("FTS: hit MAX_PAGES=%d safety cap — truncating", MAX_PAGES)
                break
            data = _get(client, url, page_params)
            releases = data.get("releases") or []
            log.info("FTS page %d: %d releases", pages_fetched + 1, len(releases))

            for release in releases:
                yield release

            pages_fetched += 1
            # Follow cursor; once we switch to links.next, drop query params
            next_url = (data.get("links") or {}).get("next")
            url = next_url or ""
            page_params = None  # cursor already encoded in next_url


def normalize_releases(releases: list[dict]) -> list[dict]:
    """Normalize a list of raw OCDS releases to TenderOpportunity field dicts.

    When multiple releases share the same ocid (amendments), keep the one with
    the latest publication_date rather than the first-seen.
    """
    result: list[dict] = []
    id_to_idx: dict[str, int] = {}
    for release in releases:
        try:
            row = normalize_fts_release(release)
        except Exception as exc:  # noqa: BLE001
            log.warning("FTS normalize error (ocid=%s): %s", release.get("ocid"), exc)
            continue
        uid = row["id"]
        if uid in id_to_idx:
            existing = result[id_to_idx[uid]]
            if row["publication_date"] > existing["publication_date"]:
                result[id_to_idx[uid]] = row
                log.debug("FTS: replaced %s with newer release", uid)
            else:
                log.debug("FTS: skipping older duplicate %s", uid)
        else:
            id_to_idx[uid] = len(result)
            result.append(row)
    return result
