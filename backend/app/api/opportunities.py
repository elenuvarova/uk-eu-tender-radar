from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, nullslast, or_, distinct
from sqlmodel import Session, select

from app.db import get_session
from app.models.tender import TenderCpv, TenderOpportunity
from app.schemas.opportunity import (
    FacetsResponse,
    CountItem,
    OpportunityDetail,
    OpportunityItem,
    OpportunityListResponse,
)

router = APIRouter(prefix="/api", tags=["opportunities"])


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
        stmt = (
            stmt.join(TenderCpv, TenderOpportunity.id == TenderCpv.tender_id)
            .where(or_(*[TenderCpv.cpv_code.startswith(p) for p in cpv]))
            .distinct()
        )

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
        stmt = stmt.where(TenderOpportunity.status.in_(status))

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

    # Sort
    if sort == "published_desc":
        stmt = stmt.order_by(TenderOpportunity.publication_date.desc())
    elif sort == "value_desc":
        stmt = stmt.order_by(
            nullslast(TenderOpportunity.estimated_value_eur.desc())
        )
    else:  # deadline_asc (default)
        stmt = stmt.order_by(
            nullslast(TenderOpportunity.deadline.asc())
        )

    stmt = stmt.offset(offset).limit(limit)
    items = session.exec(stmt).all()

    return OpportunityListResponse(
        items=[OpportunityItem.model_validate(o) for o in items],
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

    # Closing soon (deadline in next 7 days)
    now = datetime.now(timezone.utc)
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
