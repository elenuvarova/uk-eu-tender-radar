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


def _upsert_rows(session, rows: list[dict]) -> tuple[int, int, int]:
    """Insert or update TenderOpportunity + TenderCpv rows.

    Each record is committed on its own, so one malformed notice (bad JSON,
    constraint violation, type error) is rolled back and skipped instead of
    aborting the whole batch. Returns (inserted, updated, failed).
    """
    from sqlmodel import select

    from app.ingestion.cpv import build_cpv_rows
    from app.models.tender import TenderCpv, TenderOpportunity

    inserted = updated = failed = 0
    for row in rows:
        cpv_codes: list[str] = row.pop("_cpv_codes", [])
        tender_id = row["id"]
        was_update = False
        try:
            # no_autoflush + explicit flush so a constraint error surfaces in
            # THIS row's iteration (not deferred into a later row's autoflush
            # and misattributed). Count only after the flush succeeds.
            with session.no_autoflush:
                existing = session.get(TenderOpportunity, tender_id)
                if existing:
                    was_update = True
                    for k, v in row.items():
                        setattr(existing, k, v)
                    existing.updated_at = datetime.now(timezone.utc)
                else:
                    session.add(TenderOpportunity(**row))

                session.flush()

                # Replace CPV child rows
                for old in session.exec(
                    select(TenderCpv).where(TenderCpv.tender_id == tender_id)
                ).all():
                    session.delete(old)
                for cpv_row in build_cpv_rows(tender_id, cpv_codes):
                    session.add(TenderCpv(**cpv_row))

            session.commit()
        except Exception as exc:  # noqa: BLE001 — isolate one bad record
            session.rollback()
            failed += 1
            log.warning("upsert failed for %s: %s", tender_id, exc)
        else:
            updated += int(was_update)
            inserted += int(not was_update)

    return inserted, updated, failed


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
        ins, upd, failed = _upsert_rows(session, rows)
    log.info("FTS: done — inserted=%d updated=%d failed=%d", ins, upd, failed)
    _run_buyer_jobs()


def _run_buyer_jobs() -> None:
    """Run buyer resolve + rollup after any ingestion. Non-fatal: a failure here
    means buyer stats are stale but doesn't discard the ingested notices."""
    from app.db import get_session
    from app.jobs.buyer_resolve import resolve
    from app.jobs.buyer_rollup import rollup
    try:
        with next(get_session()) as session:
            created, linked = resolve(session)
            rows = rollup(session)
        log.info("Buyer jobs: resolve created=%d linked=%d rollup=%d", created, linked, rows)
    except Exception as exc:  # noqa: BLE001
        log.warning("Buyer jobs failed (non-fatal): %s", exc)


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
        ins, upd, failed = _upsert_rows(session, rows)
    log.info("TED: done — inserted=%d updated=%d failed=%d", ins, upd, failed)
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
