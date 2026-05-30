"""Buyer entity resolution layer + aggregated category stats.

buyer_id is a deterministic hash of the normalized name so the resolve job
is idempotent — running it twice produces the same Buyer records.
"""
from datetime import datetime, timezone

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Buyer(SQLModel, table=True):
    __tablename__ = "buyer"

    id: str = Field(primary_key=True)        # "B:<md5[:12]>"
    canonical_name: str
    normalized_name: str = Field(index=True) # dedup key
    country: str | None = None
    region: str | None = None
    name_aliases: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)


class BuyerCategoryStat(SQLModel, table=True):
    __tablename__ = "buyer_category_stat"

    buyer_id: str = Field(foreign_key="buyer.id", primary_key=True)
    cpv_division: str = Field(primary_key=True)   # 2-digit
    notice_count: int = 0
    awarded_count: int = 0
    avg_value_eur: float | None = None
    last_notice_date: datetime | None = None
