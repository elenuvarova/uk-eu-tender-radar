"""Core unified model. Full schema rationale in docs/DATA_MODEL.md.

Phase 0 ships TenderOpportunity + TenderCpv. The remaining tables
(Buyer, BuyerCategoryStat, SupplierProfile, SavedSearch,
RelevanceScoreCache, FxRate) land in later phases per DEV_PLAN §4.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, Index
from sqlalchemy.types import JSON
from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenderOpportunity(SQLModel, table=True):
    __tablename__ = "tender_opportunity"
    __table_args__ = (
        Index("ix_tender_deadline", "deadline"),
        Index("ix_tender_buyer_country", "buyer_country"),
        Index("ix_tender_source", "source"),
        Index("ix_tender_estimated_value", "estimated_value"),
        Index("ix_tender_status", "status"),
    )

    id: str = Field(primary_key=True)  # "UK:<ocid>" / "EU:<publication-number>"
    source: str  # "UK" | "EU"
    source_notice_id: str
    source_url: str

    title: str
    title_lang: str = "en"
    description: str | None = None

    buyer_id: str | None = Field(default=None, index=True)  # FK->Buyer (added in Phase 5)
    buyer_name: str | None = None
    buyer_country: str | None = None
    buyer_region_raw: str | None = None
    buyer_region_code: str | None = None

    estimated_value: float | None = None
    currency: str | None = None
    estimated_value_eur: float | None = None
    fx_rate_date: datetime | None = None

    publication_date: datetime
    deadline: datetime | None = None
    deadline_tz_offset: str | None = None

    notice_type: str  # PLANNING|TENDER|AWARD|CONTRACT|MODIFICATION|OTHER
    procedure_type: str  # OPEN|SELECTIVE|LIMITED|DIRECT|OTHER
    procedure_type_raw: str | None = None
    status: str  # PLANNED|OPEN|CLOSED|AWARDED|UNSUCCESSFUL|CANCELLED
    award_supplier: str | None = None

    raw_json: dict = Field(default_factory=dict, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    cpvs: list["TenderCpv"] = Relationship(
        back_populates="tender",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class TenderCpv(SQLModel, table=True):
    __tablename__ = "tender_cpv"
    __table_args__ = (
        Index("ix_tender_cpv_code", "cpv_code"),
        Index("ix_tender_cpv_division", "cpv_division"),
    )

    id: int | None = Field(default=None, primary_key=True)
    tender_id: str = Field(foreign_key="tender_opportunity.id", index=True)
    cpv_code: str
    cpv_division: str  # 2-digit

    tender: TenderOpportunity | None = Relationship(back_populates="cpvs")
