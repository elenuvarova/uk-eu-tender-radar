"""CLI entry point for ingestion jobs.

Usage:
    python -m app.ingestion.run --source fts [--days 7] [--niche-only]
    python -m app.ingestion.run --source ted [--days 1] [--niche-only]
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ingestion.run")


def _upsert_rows(session, rows: list[dict]) -> tuple[int, int]:
    """Insert or update TenderOpportunity + TenderCpv rows. Returns (inserted, updated)."""
    from sqlmodel import select

    from app.ingestion.cpv import build_cpv_rows
    from app.models.tender import TenderCpv, TenderOpportunity

    inserted = updated = 0
    for row in rows:
        cpv_codes: list[str] = row.pop("_cpv_codes", [])
        tender_id = row["id"]

        existing = session.get(TenderOpportunity, tender_id)
        if existing:
            for k, v in row.items():
                setattr(existing, k, v)
            existing.updated_at = datetime.now(timezone.utc)
            updated += 1
        else:
            session.add(TenderOpportunity(**row))
            inserted += 1

        # Replace CPV child rows
        for old in session.exec(
            select(TenderCpv).where(TenderCpv.tender_id == tender_id)
        ).all():
            session.delete(old)
        for cpv_row in build_cpv_rows(tender_id, cpv_codes):
            session.add(TenderCpv(**cpv_row))

    session.commit()
    return inserted, updated


def run_fts(days: int, niche_only: bool) -> None:
    from app.db import get_session, init_db
    from app.ingestion.cpv import is_in_niche
    from app.ingestion.fts import iter_releases, normalize_releases

    init_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    log.info("FTS: fetching releases since %s (niche_only=%s)", since.date(), niche_only)

    raw: list[dict] = list(iter_releases(updated_from=since))
    log.info("FTS: %d raw releases fetched", len(raw))

    rows = normalize_releases(raw)
    if niche_only:
        rows = [r for r in rows if is_in_niche(r.get("_cpv_codes", []))]
    log.info("FTS: %d rows to upsert", len(rows))

    with next(get_session()) as session:
        ins, upd = _upsert_rows(session, rows)
    log.info("FTS: done — inserted=%d updated=%d", ins, upd)
    _run_buyer_jobs()


def _run_buyer_jobs() -> None:
    """Run buyer resolve + rollup after any ingestion."""
    from app.db import get_session
    from app.jobs.buyer_resolve import resolve
    from app.jobs.buyer_rollup import rollup
    with next(get_session()) as session:
        created, linked = resolve(session)
        rows = rollup(session)
    log.info("Buyer jobs: resolve created=%d linked=%d rollup=%d", created, linked, rows)


def run_ted(days: int, niche_only: bool) -> None:
    from app.db import get_session, init_db
    from app.ingestion.cpv import is_in_niche
    from app.ingestion.ted import fetch_and_normalize, DEFAULT_COUNTRIES

    init_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    log.info("TED: fetching notices since %s (niche_only=%s)", since.date(), niche_only)

    # Use Tier-1 CPV divisions as API-level pre-filter when niche_only
    cpv_divisions = ["48", "72"] if niche_only else None
    rows = fetch_and_normalize(
        since=since,
        countries=DEFAULT_COUNTRIES,
        cpv_divisions=cpv_divisions,
    )
    if niche_only:
        rows = [r for r in rows if is_in_niche(r.get("_cpv_codes", []))]
    log.info("TED: %d rows to upsert", len(rows))

    with next(get_session()) as session:
        ins, upd = _upsert_rows(session, rows)
    log.info("TED: done — inserted=%d updated=%d", ins, upd)
    _run_buyer_jobs()


def main() -> None:
    parser = argparse.ArgumentParser(description="Tender Radar ingestion runner")
    parser.add_argument("--source", choices=["fts", "ted"], required=True)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--niche-only", action="store_true",
                        help="Only store notices matching the digital/edtech CPV filter")
    args = parser.parse_args()

    if args.source == "fts":
        run_fts(days=args.days, niche_only=args.niche_only)
    else:
        run_ted(days=args.days, niche_only=args.niche_only)


if __name__ == "__main__":
    main()
