from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.models.profile import SupplierProfile

router = APIRouter(prefix="/api", tags=["profile"])

_DEFAULT_ID = "default"


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
def update_profile(update: SupplierProfile, session: Session = Depends(get_session)):
    profile = _get_or_create_profile(session)
    data = update.model_dump(exclude={"id"})
    for k, v in data.items():
        setattr(profile, k, v)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile
