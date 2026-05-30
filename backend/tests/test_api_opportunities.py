"""API tests for /api/opportunities and /api/facets with an in-memory DB."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, StaticPool

from app.main import app
from app.db import get_session
from app.models.tender import TenderOpportunity, TenderCpv


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


def _make_opp(suffix: str, **overrides) -> TenderOpportunity:
    defaults = dict(
        id=f"UK:test-{suffix}",
        source="UK",
        source_notice_id=f"00{suffix}-2026",
        source_url=f"https://example.com/{suffix}",
        title=f"Test opportunity {suffix}",
        title_lang="en",
        buyer_country="GB",
        publication_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        notice_type="TENDER",
        procedure_type="OPEN",
        status="OPEN",
        raw_json={},
    )
    defaults.update(overrides)
    return TenderOpportunity(**defaults)


# ── empty DB ──────────────────────────────────────────────────────────────────

def test_opportunities_empty_db(client):
    r = client.get("/api/opportunities")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_facets_empty_db(client):
    r = client.get("/api/facets")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["by_source"] == {}
    assert body["closing_soon"] == 0


# ── with data ─────────────────────────────────────────────────────────────────

@pytest.fixture
def two_opps(session):
    opp1 = _make_opp("1", source="UK", buyer_country="GB",
                     deadline=datetime(2026, 6, 30, tzinfo=timezone.utc),
                     estimated_value=500000, currency="GBP",
                     estimated_value_eur=590000)
    opp2 = _make_opp("2", source="EU", buyer_country="DE",
                     notice_type="AWARD", status="AWARDED",
                     estimated_value=200000, currency="EUR",
                     estimated_value_eur=200000)
    session.add_all([opp1, opp2])
    session.add(TenderCpv(tender_id=opp1.id, cpv_code="72500000", cpv_division="72"))
    session.add(TenderCpv(tender_id=opp2.id, cpv_code="48000000", cpv_division="48"))
    session.commit()
    return opp1, opp2


def test_opportunities_list_count(client, two_opps):
    r = client.get("/api/opportunities")
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_opportunities_filter_by_source(client, two_opps):
    r = client.get("/api/opportunities?source=UK")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["source"] == "UK"


def test_opportunities_filter_by_country(client, two_opps):
    r = client.get("/api/opportunities?country=DE")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["buyer_country"] == "DE"


def test_opportunities_filter_by_cpv(client, two_opps):
    r = client.get("/api/opportunities?cpv=72")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == "UK:test-1"


def test_opportunities_filter_by_notice_type(client, two_opps):
    r = client.get("/api/opportunities?notice_type=AWARD")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["notice_type"] == "AWARD"


def test_opportunities_filter_by_status(client, two_opps):
    r = client.get("/api/opportunities?status=OPEN")
    body = r.json()
    assert body["total"] == 1


def test_opportunities_keyword_search(client, two_opps):
    r = client.get("/api/opportunities?q=Test+opportunity+1")
    body = r.json()
    assert body["total"] == 1


def test_opportunities_pagination(client, two_opps):
    r = client.get("/api/opportunities?limit=1&offset=0")
    body = r.json()
    assert len(body["items"]) == 1
    assert body["total"] == 2

    r2 = client.get("/api/opportunities?limit=1&offset=1")
    assert len(r2.json()["items"]) == 1


def test_opportunities_sort_published_desc(client, two_opps):
    r = client.get("/api/opportunities?sort=published_desc")
    assert r.status_code == 200


def test_opportunity_detail_404(client):
    r = client.get("/api/opportunities/nonexistent")
    assert r.status_code == 404


def test_opportunity_detail_found(client, two_opps):
    opp1, _ = two_opps
    r = client.get(f"/api/opportunities/{opp1.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == opp1.id
    assert body["cpv_codes"] == ["72500000"]


def test_facets_with_data(client, two_opps):
    r = client.get("/api/facets")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert set(body["by_source"].keys()) == {"UK", "EU"}
    assert any(c["label"] == "GB" for c in body["by_country"])
    assert any(c["label"] in ("72", "48") for c in body["by_cpv_division"])
