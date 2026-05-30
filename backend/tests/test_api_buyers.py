"""Tests for GET /api/buyers/{buyer_id}."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, StaticPool

from app.main import app
from app.db import get_session
from app.models.buyer import Buyer, BuyerCategoryStat
from app.models.tender import TenderOpportunity


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _make_buyer(session: Session) -> Buyer:
    buyer = Buyer(
        id="B:abc123456789",
        canonical_name="Example County Council",
        normalized_name="example county council",
        country="GB",
        name_aliases=["Example County Council"],
    )
    session.add(buyer)
    opp = TenderOpportunity(
        id="UK:test-buyer-opp",
        source="UK", source_notice_id="100-2026",
        source_url="https://example.com",
        title="Cloud services",
        buyer_id=buyer.id,
        buyer_name="Example County Council",
        publication_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        notice_type="TENDER", procedure_type="OPEN", status="OPEN", raw_json={},
    )
    session.add(opp)
    stat = BuyerCategoryStat(
        buyer_id=buyer.id, cpv_division="72",
        notice_count=4, awarded_count=1, avg_value_eur=600_000,
    )
    session.add(stat)
    session.commit()
    return buyer


def test_buyer_not_found(client):
    r = client.get("/api/buyers/B:nonexistent")
    assert r.status_code == 404


def test_buyer_found(client, session):
    buyer = _make_buyer(session)
    r = client.get(f"/api/buyers/{buyer.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == buyer.id
    assert body["canonical_name"] == "Example County Council"
    assert body["country"] == "GB"


def test_buyer_top_categories(client, session):
    buyer = _make_buyer(session)
    r = client.get(f"/api/buyers/{buyer.id}")
    cats = r.json()["top_categories"]
    assert len(cats) == 1
    assert cats[0]["cpv_division"] == "72"
    assert cats[0]["notice_count"] == 4


def test_buyer_recent_notices(client, session):
    buyer = _make_buyer(session)
    r = client.get(f"/api/buyers/{buyer.id}")
    notices = r.json()["recent_notices"]
    assert len(notices) == 1
    assert notices[0]["title"] == "Cloud services"


def test_buyer_aliases(client, session):
    buyer = _make_buyer(session)
    r = client.get(f"/api/buyers/{buyer.id}")
    assert "Example County Council" in r.json()["name_aliases"]
