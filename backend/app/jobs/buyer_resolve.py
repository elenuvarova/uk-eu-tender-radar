"""Buyer entity resolution job.

Reads every unique raw buyer_name from tender_opportunity where buyer_id IS NULL,
normalizes it, deduplicates, creates/reuses Buyer records, and populates buyer_id.

Normalization is intentionally lightweight: lowercase + strip legal suffixes +
collapse whitespace.  This avoids merging distinct buyers with similar names
while still catching "NHS Trust" vs "nhs trust" or "Acme Ltd" vs "Acme Limited".
"""
from __future__ import annotations

import hashlib
import logging
import re

from sqlmodel import Session, select

from app.models.buyer import Buyer
from app.models.tender import TenderOpportunity

log = logging.getLogger(__name__)

# Legal suffixes that add no disambiguation value
_SUFFIXES = re.compile(
    r"\b(ltd|limited|plc|llp|llc|inc|corp|gmbh|s\.?a|n\.?v|b\.?v|"
    r"sarl|a\.?g|s\.?r\.?l|s\.?l|sas|aps|oy|ab|pte|pty)\b",
    re.IGNORECASE,
)


def normalize_name(raw: str) -> str:
    """Produce a canonical form of a buyer name for deduplication."""
    n = raw.lower().strip()
    n = re.sub(r"[^\w\s]", " ", n)       # strip punctuation
    n = _SUFFIXES.sub(" ", n)             # remove legal suffixes
    n = re.sub(r"\s+", " ", n).strip()   # collapse whitespace
    return n


def make_buyer_id(normalized: str, country: str | None = None) -> str:
    """Deterministic, stable ID from the normalized name + country.

    Country is included to prevent same-named buyers in different countries
    (e.g. "Department of Health" GB vs IE) from collapsing into one entity.
    """
    key = f"{country or ''}:{normalized}"
    digest = hashlib.md5(key.encode()).hexdigest()[:12]
    return f"B:{digest}"


def _reset_stale_links(session: Session) -> int:
    """Null out buyer_id on rows whose stored id no longer matches the current
    make_buyer_id scheme (e.g. after the hash gained the country component), so
    they get re-resolved below. Without this, a scheme change would split one
    buyer across an old and a new id and fragment its history. Idempotent: once
    every row matches the current scheme, this is a no-op.
    """
    reset = 0
    rows = session.exec(
        select(TenderOpportunity).where(
            TenderOpportunity.buyer_name.isnot(None),
            TenderOpportunity.buyer_id.isnot(None),
        )
    ).all()
    for opp in rows:
        norm = normalize_name(opp.buyer_name or "")
        if not norm:
            continue
        if opp.buyer_id != make_buyer_id(norm, opp.buyer_country):
            opp.buyer_id = None
            session.add(opp)
            reset += 1
    if reset:
        # Drop now-orphaned Buyer rows that no live opportunity references.
        live_ids = {
            r for (r,) in session.exec(
                select(TenderOpportunity.buyer_id).where(
                    TenderOpportunity.buyer_id.isnot(None)
                ).distinct()
            ).all()
        }
        for buyer in session.exec(select(Buyer)).all():
            if buyer.id not in live_ids:
                session.delete(buyer)
        session.commit()
        log.info("buyer_resolve: reset %d rows to re-resolve under current scheme", reset)
    return reset


def resolve(session: Session, batch_size: int = 500) -> tuple[int, int]:
    """
    Assign buyer_id to all TenderOpportunity rows that have a buyer_name
    but no buyer_id.  Returns (created, linked) counts.
    """
    created = linked = 0

    # Heal any rows resolved under a previous make_buyer_id scheme first.
    _reset_stale_links(session)

    # Fetch distinct unresolved names
    stmt = (
        select(TenderOpportunity.buyer_name, TenderOpportunity.buyer_country)
        .where(
            TenderOpportunity.buyer_name.isnot(None),
            TenderOpportunity.buyer_id.is_(None),
        )
        .distinct()
    )
    unresolved = session.exec(stmt).all()
    log.info("buyer_resolve: %d distinct unresolved names", len(unresolved))

    for raw_name, country in unresolved:
        if not raw_name:
            continue
        norm = normalize_name(raw_name)
        if not norm:
            continue

        bid = make_buyer_id(norm, country)

        # Reuse existing Buyer or create
        buyer = session.get(Buyer, bid)
        if not buyer:
            buyer = Buyer(
                id=bid,
                canonical_name=raw_name,
                normalized_name=norm,
                country=country,
                name_aliases=[raw_name],
            )
            session.add(buyer)
            created += 1
        else:
            # Register alias if new spelling
            aliases = buyer.name_aliases or []
            if raw_name not in aliases:
                aliases.append(raw_name)
                buyer.name_aliases = aliases
                session.add(buyer)

        # Bulk-update all matching rows
        opps = session.exec(
            select(TenderOpportunity).where(
                TenderOpportunity.buyer_name == raw_name,
                TenderOpportunity.buyer_id.is_(None),
            )
        ).all()
        for opp in opps:
            opp.buyer_id = bid
            session.add(opp)
        linked += len(opps)

    session.commit()
    log.info("buyer_resolve: created=%d linked=%d", created, linked)
    return created, linked
