"""Buyer category stats rollup job.

Aggregates TenderOpportunity × TenderCpv into BuyerCategoryStat per
(buyer_id, cpv_division).  Run after buyer_resolve to power C5 scoring
and the buyer profile page.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlmodel import Session, select, delete

from app.models.buyer import BuyerCategoryStat
from app.models.tender import TenderCpv, TenderOpportunity

log = logging.getLogger(__name__)


def rollup(session: Session) -> int:
    """Recompute BuyerCategoryStat from scratch. Returns number of rows written."""

    # Fetch all opps that have a buyer_id (post-resolve)
    opps = session.exec(
        select(TenderOpportunity).where(TenderOpportunity.buyer_id.isnot(None))
    ).all()

    if not opps:
        log.info("buyer_rollup: no resolved opportunities, skipping")
        return 0

    opp_ids = [o.id for o in opps]
    opp_map = {o.id: o for o in opps}

    cpv_rows = session.exec(
        select(TenderCpv).where(TenderCpv.tender_id.in_(opp_ids))
    ).all()

    # Group: (buyer_id, cpv_division) → set of distinct opportunity ids.
    # A notice can carry several CPV codes in the SAME division (e.g. 72500000
    # and 72600000); grouping per cpv_row would then count that one notice
    # twice in notice_count and skew awarded_count / avg_value / last_date.
    # Dedupe by opportunity id so each notice counts once per division.
    group_ids: dict[tuple, set] = defaultdict(set)
    for cpv_row in cpv_rows:
        opp = opp_map.get(cpv_row.tender_id)
        if opp and opp.buyer_id:
            group_ids[(opp.buyer_id, cpv_row.cpv_division)].add(opp.id)

    # Delete existing stats and rewrite
    session.exec(delete(BuyerCategoryStat))

    rows_written = 0
    for (buyer_id, div), opp_id_set in group_ids.items():
        group_opps = [opp_map[oid] for oid in opp_id_set]
        awarded = [o for o in group_opps if o.status == "AWARDED"]
        values = [o.estimated_value_eur for o in group_opps if o.estimated_value_eur]
        dates = [o.publication_date for o in group_opps if o.publication_date]

        stat = BuyerCategoryStat(
            buyer_id=buyer_id,
            cpv_division=div,
            notice_count=len(group_opps),
            awarded_count=len(awarded),
            avg_value_eur=sum(values) / len(values) if values else None,
            last_notice_date=max(dates) if dates else None,
        )
        session.add(stat)
        rows_written += 1

    session.commit()
    log.info("buyer_rollup: wrote %d BuyerCategoryStat rows", rows_written)
    return rows_written
