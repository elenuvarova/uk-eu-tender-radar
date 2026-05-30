from datetime import datetime
from pydantic import BaseModel, ConfigDict


class RelevanceScore(BaseModel):
    score: int          # 0-100
    reasons: list[str]


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
    relevance: RelevanceScore | None = None


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
