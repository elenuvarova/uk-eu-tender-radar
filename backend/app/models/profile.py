from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class SupplierProfile(SQLModel, table=True):
    __tablename__ = "supplier_profile"

    id: str = Field(default="default", primary_key=True)
    name: str = "My Company"

    # Scoring lens (all arrays stored as JSON)
    target_cpv_codes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Value band (stored in value_currency; compared against estimated_value_eur when EUR)
    value_min: float | None = None
    value_max: float | None = None
    value_currency: str = "EUR"

    # Hard pre-filter: only score opportunities from these countries
    target_countries: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    min_days_to_bid: int = 7


class SavedSearch(SQLModel, table=True):
    __tablename__ = "saved_search"

    id: str = Field(primary_key=True)
    name: str
    filters_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    alert_enabled: bool = False
