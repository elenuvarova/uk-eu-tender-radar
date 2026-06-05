from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlmodel import Session

from app.db import get_session
from app.models.profile import SupplierProfile

router = APIRouter(prefix="/api", tags=["profile"])

_DEFAULT_ID = "default"


class ProfileUpdate(BaseModel):
    """Validated request body for PUT /api/profile.

    Kept separate from the SupplierProfile table model so client input can't set
    arbitrary fields and is range-checked before it reaches the scorer
    (value_min=0 / value_max<value_min would otherwise break score_value).
    """

    # Length caps below bound request size (DoS) and keep list items sane before
    # they reach the scorer. Caps are generous relative to real profiles.
    name: str | None = Field(default=None, max_length=200)
    target_cpv_codes: list[str] | None = Field(default=None, max_length=100)
    keywords: list[str] | None = Field(default=None, max_length=100)
    value_min: float | None = None
    value_max: float | None = None
    value_currency: str | None = Field(default=None, max_length=8)
    target_countries: list[str] | None = Field(default=None, max_length=100)
    # Upper clamp (<=60) keeps the score_deadline ramp inside its design range:
    # values >38 would skip the comfortable-window plateau (ramp_top > 45).
    min_days_to_bid: int | None = Field(default=None, ge=0, le=60)

    @field_validator("value_min", "value_max")
    @classmethod
    def _non_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("value must be >= 0")
        return v

    @field_validator("target_cpv_codes", "keywords", "target_countries")
    @classmethod
    def _cap_item_lengths(cls, v: list[str] | None) -> list[str] | None:
        # Bound each element so a single 100-item list can't carry megabytes.
        if v is not None:
            for item in v:
                if len(item) > 64:
                    raise ValueError("list item exceeds 64 characters")
        return v

    @model_validator(mode="after")
    def _range_ordered(self) -> "ProfileUpdate":
        if (
            self.value_min is not None
            and self.value_max is not None
            and self.value_max < self.value_min
        ):
            raise ValueError("value_max must be >= value_min")
        return self


def _get_or_create_profile(session: Session) -> SupplierProfile:
    profile = session.get(SupplierProfile, _DEFAULT_ID)
    if not profile:
        profile = SupplierProfile(id=_DEFAULT_ID)
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


@router.get("/profile", response_model=SupplierProfile)
def get_profile(session: Session = Depends(get_session)):
    return _get_or_create_profile(session)


@router.put("/profile", response_model=SupplierProfile)
def update_profile(update: ProfileUpdate, session: Session = Depends(get_session)):
    profile = _get_or_create_profile(session)
    for k, v in update.model_dump(exclude_unset=True).items():
        setattr(profile, k, v)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile
