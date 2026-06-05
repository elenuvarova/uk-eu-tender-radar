"""Tests for /api/profile and scoring integration."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, StaticPool

from app.main import app
from app.db import get_session


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


def test_get_profile_default(client):
    r = client.get("/api/profile")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "default"
    assert body["target_cpv_codes"] == []
    assert body["keywords"] == []


def test_put_profile(client):
    payload = {
        "id": "default",
        "name": "Test Co",
        "target_cpv_codes": ["72000000", "48000000"],
        "keywords": ["cloud", "digital"],
        "value_min": 100000,
        "value_max": 1000000,
        "value_currency": "EUR",
        "target_countries": ["GB", "DE"],
        "min_days_to_bid": 10,
    }
    r = client.put("/api/profile", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["target_cpv_codes"] == ["72000000", "48000000"]
    assert body["keywords"] == ["cloud", "digital"]


def test_put_profile_rejects_oversized_name(client):
    r = client.put("/api/profile", json={"name": "x" * 201})
    assert r.status_code == 422


def test_put_profile_rejects_too_many_cpv_codes(client):
    r = client.put("/api/profile", json={"target_cpv_codes": ["72000000"] * 101})
    assert r.status_code == 422


def test_put_profile_rejects_oversized_list_item(client):
    r = client.put("/api/profile", json={"keywords": ["k" * 65]})
    assert r.status_code == 422


def test_put_profile_rejects_min_days_over_cap(client):
    r = client.put("/api/profile", json={"min_days_to_bid": 61})
    assert r.status_code == 422


def test_put_profile_rejects_negative_min_days(client):
    r = client.put("/api/profile", json={"min_days_to_bid": -1})
    assert r.status_code == 422


def test_opportunities_query_rejects_oversized_q(client):
    r = client.get("/api/opportunities", params={"q": "x" * 201})
    assert r.status_code == 422


def test_opportunities_with_scoring(client, session):
    from datetime import datetime, timedelta, timezone
    from app.models.tender import TenderOpportunity, TenderCpv
    from app.models.profile import SupplierProfile

    # Create a profile
    profile = SupplierProfile(
        id="default", target_cpv_codes=["72000000"],
        keywords=["cloud"], value_min=100000, value_max=2000000,
    )
    session.add(profile)

    # Create an opportunity
    opp = TenderOpportunity(
        id="UK:score-test", source="UK",
        source_notice_id="123-2026", source_url="https://example.com",
        title="Cloud services procurement",
        publication_date=datetime.now(timezone.utc),
        deadline=datetime.now(timezone.utc) + timedelta(days=21),
        estimated_value_eur=500000,
        notice_type="TENDER", procedure_type="OPEN", status="OPEN",
        raw_json={},
    )
    session.add(opp)
    session.add(TenderCpv(tender_id=opp.id, cpv_code="72000000", cpv_division="72"))
    session.commit()

    r = client.get("/api/opportunities?score=true")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["relevance"] is not None
    assert 0 <= items[0]["relevance"]["score"] <= 100
    assert len(items[0]["relevance"]["reasons"]) == 5


def test_opportunities_without_scoring_no_relevance(client, session):
    from datetime import datetime, timezone
    from app.models.tender import TenderOpportunity
    opp = TenderOpportunity(
        id="UK:no-score", source="UK", source_notice_id="124-2026",
        source_url="https://example.com", title="Test",
        publication_date=datetime.now(timezone.utc),
        notice_type="TENDER", procedure_type="OPEN", status="OPEN", raw_json={},
    )
    session.add(opp); session.commit()

    r = client.get("/api/opportunities")  # no score=true
    items = r.json()["items"]
    assert items[0]["relevance"] is None


def test_detail_scored_when_profile_exists(client, session):
    """GET /api/opportunities/{id} attaches a relevance score when a default
    profile exists, so the drawer's score breakdown can render."""
    from datetime import datetime, timedelta, timezone
    from app.models.tender import TenderOpportunity, TenderCpv
    from app.models.profile import SupplierProfile

    session.add(SupplierProfile(
        id="default", target_cpv_codes=["72000000"],
        keywords=["cloud"], value_min=100000, value_max=2000000,
    ))
    opp = TenderOpportunity(
        id="UK:detail-score", source="UK",
        source_notice_id="200-2026", source_url="https://example.com",
        title="Cloud services procurement",
        publication_date=datetime.now(timezone.utc),
        deadline=datetime.now(timezone.utc) + timedelta(days=21),
        estimated_value_eur=500000,
        notice_type="TENDER", procedure_type="OPEN", status="OPEN", raw_json={},
    )
    session.add(opp)
    session.add(TenderCpv(tender_id=opp.id, cpv_code="72000000", cpv_division="72"))
    session.commit()

    body = client.get(f"/api/opportunities/{opp.id}").json()
    assert body["relevance"] is not None
    assert 0 <= body["relevance"]["score"] <= 100
    assert len(body["relevance"]["reasons"]) == 5
    assert set(body["relevance"]["breakdown"]) == {"sCPV", "sKW", "sVAL", "sDDL", "sBUY"}


def test_detail_unscored_without_profile(client, session):
    """No default profile → no relevance on the detail (drawer shows nothing)."""
    from datetime import datetime, timezone
    from app.models.tender import TenderOpportunity

    opp = TenderOpportunity(
        id="UK:detail-noscore", source="UK", source_notice_id="201-2026",
        source_url="https://example.com", title="Test",
        publication_date=datetime.now(timezone.utc),
        notice_type="TENDER", procedure_type="OPEN", status="OPEN", raw_json={},
    )
    session.add(opp); session.commit()

    body = client.get(f"/api/opportunities/{opp.id}").json()
    assert body["relevance"] is None
