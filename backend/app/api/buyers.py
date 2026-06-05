from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models.buyer import Buyer, BuyerCategoryStat
from app.models.tender import TenderOpportunity
from app.timeutil import ensure_utc

router = APIRouter(prefix="/api", tags=["buyers"])


class CategoryStat(BaseModel):
    cpv_division: str
    notice_count: int
    awarded_count: int
    avg_value_eur: float | None


class RecentNotice(BaseModel):
    id: str
    title: str
    source: str
    publication_date: str
    source_url: str


class BuyerProfile(BaseModel):
    id: str
    canonical_name: str
    country: str | None
    region: str | None
    name_aliases: list[str]
    top_categories: list[CategoryStat]
    recent_notices: list[RecentNotice]


@router.get("/buyers/{buyer_id}", response_model=BuyerProfile)
def get_buyer(buyer_id: str, session: Session = Depends(get_session)):
    buyer = session.get(Buyer, buyer_id)
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")

    stats = session.exec(
        select(BuyerCategoryStat)
        .where(BuyerCategoryStat.buyer_id == buyer_id)
        .order_by(BuyerCategoryStat.notice_count.desc())
        .limit(10)
    ).all()

    recent = session.exec(
        select(TenderOpportunity)
        .where(TenderOpportunity.buyer_id == buyer_id)
        .order_by(TenderOpportunity.publication_date.desc())
        .limit(5)
    ).all()

    return BuyerProfile(
        id=buyer.id,
        canonical_name=buyer.canonical_name,
        country=buyer.country,
        region=buyer.region,
        name_aliases=buyer.name_aliases or [],
        top_categories=[
            CategoryStat(
                cpv_division=s.cpv_division,
                notice_count=s.notice_count,
                awarded_count=s.awarded_count,
                avg_value_eur=s.avg_value_eur,
            )
            for s in stats
        ],
        recent_notices=[
            RecentNotice(
                id=o.id,
                title=o.title,
                source=o.source,
                # ensure_utc so the emitted ISO carries an explicit +00:00
                # offset (naive DB value would otherwise parse as local time).
                publication_date=ensure_utc(o.publication_date).isoformat(),
                source_url=o.source_url,
            )
            for o in recent
        ],
    )
