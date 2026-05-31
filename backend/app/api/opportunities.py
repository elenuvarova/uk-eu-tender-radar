from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, nullslast, or_, distinct
from sqlmodel import Session, select

from app.db import get_session
from app.timeutil import ensure_utc
from app.models.tender import TenderCpv, TenderOpportunity
from app.models.profile import SupplierProfile
from app.models.buyer import BuyerCategoryStat
from app.schemas.opportunity import (
    FacetsResponse,
    CountItem,
    OpportunityDetail,
    OpportunityItem,
    OpportunityListResponse,
    RelevanceScore,
)

router = APIRouter(prefix="/api", tags=["opportunities"])


def _compute_effective_status(opp: TenderOpportunity) -> str:
    """CLOSED is synthetic: OPEN with deadline already passed."""
    if opp.status == "OPEN" and opp.deadline:
        if ensure_utc(opp.deadline) < datetime.now(timezone.utc):
            return "CLOSED"
    return opp.status


def _build_stmt(
    source: str | None,
    country: list[str],
    cpv: list[str],
    q: str | None,
    deadline_from: datetime | None,
    deadline_to: datetime | None,
    value_min: float | None,
    value_max: float | None,
    include_unspecified_value: bool,
    notice_type: list[str],
    status: list[str],
):
    stmt = select(TenderOpportunity)

    if source:
        stmt = stmt.where(TenderOpportunity.source == source.upper())

    if country:
        stmt = stmt.where(TenderOpportunity.buyer_country.in_(country))

    if cpv:
        # EXISTS subquery instead of join+DISTINCT: avoids row multiplication and,
        # critically, avoids SELECT DISTINCT over the raw_json column, which
        # Postgres rejects ("no equality operator for type json").
        cpv_subq = select(TenderCpv.tender_id).where(
            or_(*[TenderCpv.cpv_code.startswith(p) for p in cpv])
        )
        stmt = stmt.where(TenderOpportunity.id.in_(cpv_subq))

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                TenderOpportunity.title.ilike(like),
                TenderOpportunity.description.ilike(like),
            )
        )

    if deadline_from:
        stmt = stmt.where(TenderOpportunity.deadline >= deadline_from)
    if deadline_to:
        stmt = stmt.where(TenderOpportunity.deadline <= deadline_to)

    if value_min is not None or value_max is not None:
        value_conditions = []
        if include_unspecified_value:
            value_conditions.append(TenderOpportunity.estimated_value_eur.is_(None))
        if value_min is not None:
            value_conditions.append(TenderOpportunity.estimated_value_eur >= value_min)
        if value_max is not None:
            value_conditions.append(TenderOpportunity.estimated_value_eur <= value_max)
        if value_conditions:
            stmt = stmt.where(or_(*value_conditions))

    if notice_type:
        stmt = stmt.where(TenderOpportunity.notice_type.in_(notice_type))

    if status:
        # CLOSED is synthetic (OPEN + deadline passed) and OPEN must exclude
        # those, so resolve effective status here rather than matching the
        # stored column literally.
        # Use naive UTC to match the TIMESTAMP WITHOUT TIME ZONE DB column.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        conds = []
        plain = [s for s in status if s not in ("OPEN", "CLOSED")]
        if plain:
            conds.append(TenderOpportunity.status.in_(plain))
        if "OPEN" in status:
            conds.append(
                and_(
                    TenderOpportunity.status == "OPEN",
                    or_(
                        TenderOpportunity.deadline.is_(None),
                        TenderOpportunity.deadline >= now,
                    ),
                )
            )
        if "CLOSED" in status:
            conds.append(
                and_(
                    TenderOpportunity.status == "OPEN",
                    TenderOpportunity.deadline.isnot(None),
                    TenderOpportunity.deadline < now,
                )
            )
        if conds:
            stmt = stmt.where(or_(*conds))

    return stmt


@router.get("/opportunities", response_model=OpportunityListResponse)
def list_opportunities(
    source: str | None = None,
    country: list[str] = Query(default=[]),
    cpv: list[str] = Query(default=[]),
    q: str | None = None,
    deadline_from: datetime | None = None,
    deadline_to: datetime | None = None,
    value_min: float | None = None,
    value_max: float | None = None,
    include_unspecified_value: bool = True,
    notice_type: list[str] = Query(default=[]),
    status: list[str] = Query(default=[]),
    sort: str = "deadline_asc",
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    score: bool = False,   # attach relevance scores using the stored profile
    session: Session = Depends(get_session),
):
    stmt = _build_stmt(
        source, country, cpv, q, deadline_from, deadline_to,
        value_min, value_max, include_unspecified_value,
        notice_type, status,
    )

    # Count total (re-use same filters)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.exec(count_stmt).one()

    # Sort — append id as a tiebreaker so OFFSET/LIMIT paging is stable on
    # Postgres (ties on a non-unique sort key can otherwise skip/repeat rows).
    if sort == "published_desc":
        stmt = stmt.order_by(
            TenderOpportunity.publication_date.desc(), TenderOpportunity.id.asc()
        )
    elif sort == "published_asc":
        stmt = stmt.order_by(
            TenderOpportunity.publication_date.asc(), TenderOpportunity.id.asc()
        )
    elif sort == "value_desc":
        stmt = stmt.order_by(
            nullslast(TenderOpportunity.estimated_value_eur.desc()),
            TenderOpportunity.id.asc(),
        )
    elif sort == "value_asc":
        stmt = stmt.order_by(
            nullslast(TenderOpportunity.estimated_value_eur.asc()),
            TenderOpportunity.id.asc(),
        )
    elif sort == "deadline_desc":
        stmt = stmt.order_by(
            nullslast(TenderOpportunity.deadline.desc()), TenderOpportunity.id.asc()
        )
    else:  # deadline_asc (default)
        stmt = stmt.order_by(
            nullslast(TenderOpportunity.deadline.asc()), TenderOpportunity.id.asc()
        )

    stmt = stmt.offset(offset).limit(limit)
    items = session.exec(stmt).all()

    # Attach relevance scores if requested
    profile: SupplierProfile | None = None
    cpv_map: dict[str, list[str]] = {}
    buyer_stat_map: dict[str, int] = {}   # buyer_id → total match-CPV notices
    if score and items:
        profile = session.get(SupplierProfile, "default")
        opp_ids = [o.id for o in items]

        # Bulk CPV fetch
        cpv_rows = session.exec(
            select(TenderCpv).where(TenderCpv.tender_id.in_(opp_ids))
        ).all()
        for row in cpv_rows:
            cpv_map.setdefault(row.tender_id, []).append(row.cpv_code)

        # Bulk buyer stats fetch (C5)
        if profile:
            profile_divs = list({c[:2] for c in (profile.target_cpv_codes or [])})
            buyer_ids = [o.buyer_id for o in items if o.buyer_id]
            if buyer_ids and profile_divs:
                stat_rows = session.exec(
                    select(BuyerCategoryStat).where(
                        BuyerCategoryStat.buyer_id.in_(buyer_ids),
                        BuyerCategoryStat.cpv_division.in_(profile_divs),
                    )
                ).all()
                for s in stat_rows:
                    buyer_stat_map[s.buyer_id] = (
                        buyer_stat_map.get(s.buyer_id, 0) + s.notice_count
                    )

    def _to_item(o: TenderOpportunity) -> OpportunityItem:
        item = OpportunityItem.model_validate(o)
        item.status = _compute_effective_status(o)  # CLOSED is synthetic
        if profile:
            from app.scoring.relevance import compute_score
            # C5: None if buyer not resolved, 0 if resolved but no matching history
            if o.buyer_id:
                match_count = buyer_stat_map.get(o.buyer_id, 0)
            else:
                match_count = None
            result = compute_score(
                tender_cpvs=cpv_map.get(o.id, []),
                title=o.title,
                description=o.description,
                deadline=o.deadline,
                estimated_value_eur=o.estimated_value_eur,
                buyer_name=o.buyer_name,
                profile_cpv_codes=profile.target_cpv_codes or [],
                profile_keywords=profile.keywords or [],
                profile_value_min=profile.value_min,
                profile_value_max=profile.value_max,
                profile_min_days_to_bid=profile.min_days_to_bid,
                buyer_match_count=match_count,
            )
            item.relevance = RelevanceScore(
                score=result.score, reasons=result.reasons, breakdown=result.breakdown
            )
        return item

    return OpportunityListResponse(
        items=[_to_item(o) for o in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity(opportunity_id: str, session: Session = Depends(get_session)):
    opp = session.get(TenderOpportunity, opportunity_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Not found")

    cpv_rows = session.exec(
        select(TenderCpv).where(TenderCpv.tender_id == opportunity_id)
    ).all()
    cpv_codes = [r.cpv_code for r in cpv_rows]

    detail = OpportunityDetail.model_validate(opp)
    detail.cpv_codes = cpv_codes
    return detail


@router.get("/facets", response_model=FacetsResponse)
def get_facets(session: Session = Depends(get_session)):
    total = session.exec(select(func.count(TenderOpportunity.id))).one()

    # By source
    by_source_rows = session.exec(
        select(TenderOpportunity.source, func.count(TenderOpportunity.id))
        .group_by(TenderOpportunity.source)
    ).all()
    by_source = {row[0]: row[1] for row in by_source_rows}

    # By country (top 15)
    by_country_rows = session.exec(
        select(TenderOpportunity.buyer_country, func.count(TenderOpportunity.id))
        .where(TenderOpportunity.buyer_country.isnot(None))
        .group_by(TenderOpportunity.buyer_country)
        .order_by(func.count(TenderOpportunity.id).desc())
        .limit(15)
    ).all()
    by_country = [CountItem(label=row[0], count=row[1]) for row in by_country_rows]

    # By CPV division (top 10)
    by_cpv_rows = session.exec(
        select(TenderCpv.cpv_division, func.count(distinct(TenderCpv.tender_id)))
        .group_by(TenderCpv.cpv_division)
        .order_by(func.count(distinct(TenderCpv.tender_id)).desc())
        .limit(10)
    ).all()
    by_cpv_division = [CountItem(label=row[0], count=row[1]) for row in by_cpv_rows]

    # Closing soon (deadline in next 7 days). Naive UTC matches the DB column type.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    soon = now + timedelta(days=7)
    closing_soon = session.exec(
        select(func.count(TenderOpportunity.id)).where(
            TenderOpportunity.deadline >= now,
            TenderOpportunity.deadline <= soon,
        )
    ).one()

    return FacetsResponse(
        total=total,
        by_source=by_source,
        by_country=by_country,
        by_cpv_division=by_cpv_division,
        closing_soon=closing_soon,
    )
