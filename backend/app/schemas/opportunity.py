from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_serializer

from app.timeutil import ensure_utc


class RelevanceScore(BaseModel):
    score: int          # 0-100
    reasons: list[str]
    # Per-component sub-scores (0–1): sCPV, sKW, sVAL, sDDL, sBUY. Drives the
    # score-breakdown rail on the client.
    breakdown: dict[str, float] | None = None


class OpportunityItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    source_url: str
    title: str
    buyer_name: str | None
    buyer_country: str | None
    buyer_region_code: str | None
    estimated_value: float | None
    currency: str | None
    estimated_value_eur: float | None
    publication_date: datetime
    deadline: datetime | None
    notice_type: str
    procedure_type: str
    status: str
    award_supplier: str | None
    buyer_id: str | None = None    # set after buyer_resolve job runs
    relevance: RelevanceScore | None = None

    @field_serializer("publication_date", "deadline")
    def _serialize_utc(self, v: datetime | None) -> str | None:
        # DB columns are TIMESTAMP WITHOUT TIME ZONE and return naive datetimes.
        # Without an explicit offset the client's `new Date(iso)` parses the
        # string as LOCAL time, shifting every deadline for non-UTC users. Emit
        # an explicit +00:00 suffix so the instant is unambiguous.
        if v is None:
            return None
        return ensure_utc(v).isoformat()


class OpportunityDetail(OpportunityItem):
    description: str | None
    procedure_type_raw: str | None
    buyer_region_raw: str | None
    cpv_codes: list[str] = []


class CountItem(BaseModel):
    label: str
    count: int


class FacetsResponse(BaseModel):
    total: int
    by_source: dict[str, int]
    by_country: list[CountItem]
    by_cpv_division: list[CountItem]
    closing_soon: int  # deadline within 7 days


class OpportunityListResponse(BaseModel):
    items: list[OpportunityItem]
    total: int
    offset: int
    limit: int
