"""Tests for buyer entity resolution and rollup jobs."""
from datetime import datetime, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine, StaticPool

from app.jobs.buyer_resolve import make_buyer_id, normalize_name, resolve
from app.jobs.buyer_rollup import rollup
from app.models.buyer import Buyer, BuyerCategoryStat
from app.models.tender import TenderCpv, TenderOpportunity


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _opp(id_, buyer_name, **kw):
    defaults = dict(
        source="UK", source_notice_id=id_, source_url="https://x.com",
        title=f"Title {id_}", publication_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        notice_type="TENDER", procedure_type="OPEN", status="OPEN", raw_json={},
    )
    defaults.update(kw)
    return TenderOpportunity(id=id_, buyer_name=buyer_name, **defaults)


# ── normalize_name ────────────────────────────────────────────────────────────

def test_normalize_lowercase():
    assert normalize_name("London Borough of Haringey") == "london borough of haringey"


def test_normalize_strips_ltd():
    assert normalize_name("Acme Ltd") == "acme"


def test_normalize_strips_limited():
    assert normalize_name("Acme Limited") == "acme"


def test_normalize_strips_plc():
    assert normalize_name("BigCo PLC") == "bigco"


def test_normalize_strips_punctuation():
    n = normalize_name("Smith & Sons, Ltd.")
    assert "&" not in n
    assert "." not in n
    assert "," not in n


def test_normalize_collapses_whitespace():
    n = normalize_name("  Too   Many   Spaces  ")
    assert "  " not in n
    assert n == n.strip()


def test_normalize_empty():
    assert normalize_name("") == ""


def test_normalize_gmbh():
    n = normalize_name("Siemens GmbH")
    assert "gmbh" not in n
    assert "siemens" in n


# ── make_buyer_id ─────────────────────────────────────────────────────────────

def test_buyer_id_deterministic():
    assert make_buyer_id("acme") == make_buyer_id("acme")


def test_buyer_id_format():
    bid = make_buyer_id("acme")
    assert bid.startswith("B:")
    assert len(bid) == 14  # "B:" + 12 hex


def test_buyer_id_different_names():
    assert make_buyer_id("acme") != make_buyer_id("globex")


def test_buyer_id_country_disambiguates():
    # Same name, different country -> different id; same name+country -> stable
    assert make_buyer_id("dept of health", "GB") != make_buyer_id("dept of health", "IE")
    assert make_buyer_id("dept of health", "GB") == make_buyer_id("dept of health", "GB")


# ── resolve ───────────────────────────────────────────────────────────────────

def test_resolve_creates_buyers(session):
    session.add(_opp("UK:1", "London Borough of Haringey"))
    session.add(_opp("UK:2", "Manchester City Council"))
    session.commit()

    created, linked = resolve(session)
    assert created == 2
    assert linked == 2

    buyers = session.exec(Buyer.__table__.select()).fetchall()
    assert len(buyers) == 2


def test_resolve_sets_buyer_id(session):
    opp = _opp("UK:1", "Acme Ltd")
    session.add(opp); session.commit()

    resolve(session)
    session.refresh(opp)
    assert opp.buyer_id is not None
    assert opp.buyer_id.startswith("B:")


def test_resolve_deduplicates_same_buyer(session):
    session.add(_opp("UK:1", "Acme Ltd"))
    session.add(_opp("UK:2", "Acme Ltd"))
    session.commit()

    created, linked = resolve(session)
    assert created == 1   # only one Buyer record
    assert linked == 2    # both opps linked


def test_resolve_idempotent(session):
    session.add(_opp("UK:1", "Acme Ltd"))
    session.commit()

    resolve(session)
    created2, linked2 = resolve(session)
    # Second run finds no unresolved names
    assert created2 == 0
    assert linked2 == 0


def test_resolve_merges_aliases(session):
    """Same normalized name → same Buyer, both spellings as aliases."""
    session.add(_opp("UK:1", "NHS Trust"))
    session.add(_opp("UK:2", "NHS Trust"))
    session.commit()

    resolve(session)
    buyer_id = make_buyer_id(normalize_name("NHS Trust"), None)
    buyer = session.get(Buyer, buyer_id)
    assert buyer is not None
    assert "NHS Trust" in buyer.name_aliases


def test_resolve_splits_same_name_across_countries(session):
    """Same buyer name in two countries → two distinct Buyer records."""
    session.add(_opp("UK:1", "Department of Health", buyer_country="GB"))
    session.add(_opp("IE:1", "Department of Health", buyer_country="IE"))
    session.commit()

    created, linked = resolve(session)
    assert created == 2
    assert linked == 2
    ids = {o.buyer_id for o in session.exec(TenderOpportunity.__table__.select()).fetchall()}
    assert len(ids) == 2


def test_resolve_heals_stale_scheme_links(session):
    """A row resolved under the old name-only scheme is re-resolved under the
    current name+country scheme, and its orphaned Buyer is dropped."""
    opp = _opp("UK:1", "Acme Ltd", buyer_country="GB")
    # Simulate a row resolved under the old name-only hash (no country)
    old_id = make_buyer_id(normalize_name("Acme Ltd"))
    opp.buyer_id = old_id
    session.add(opp)
    session.add(Buyer(
        id=old_id, canonical_name="Acme Ltd",
        normalized_name=normalize_name("Acme Ltd"), country="GB",
        name_aliases=["Acme Ltd"],
    ))
    session.commit()

    resolve(session)

    new_id = make_buyer_id(normalize_name("Acme Ltd"), "GB")
    refreshed = session.get(TenderOpportunity, "UK:1")
    assert refreshed.buyer_id == new_id
    # Old orphaned buyer gone; exactly one buyer remains
    buyers = session.exec(Buyer.__table__.select()).fetchall()
    assert len(buyers) == 1
    assert buyers[0].id == new_id


# ── rollup ────────────────────────────────────────────────────────────────────

def test_rollup_creates_stats(session):
    opp = _opp("UK:1", "Acme Ltd", estimated_value_eur=500_000, status="OPEN")
    session.add(opp); session.commit()
    resolve(session)
    session.add(TenderCpv(tender_id=opp.id, cpv_code="72500000", cpv_division="72"))
    session.commit()

    rows = rollup(session)
    assert rows == 1

    stats = session.exec(BuyerCategoryStat.__table__.select()).fetchall()
    assert len(stats) == 1
    assert stats[0].cpv_division == "72"
    assert stats[0].notice_count == 1


def test_rollup_aggregates_multiple_opps(session):
    for i in range(3):
        opp = _opp(f"UK:{i}", "Acme Ltd")
        session.add(opp)
    session.commit()
    resolve(session)
    for i in range(3):
        session.add(TenderCpv(tender_id=f"UK:{i}", cpv_code="72000000", cpv_division="72"))
    session.commit()

    rollup(session)
    stat = session.exec(
        BuyerCategoryStat.__table__.select()
    ).fetchone()
    assert stat.notice_count == 3


def test_rollup_empty_db(session):
    rows = rollup(session)
    assert rows == 0


def test_rollup_dedups_same_division_cpvs_on_one_notice(session):
    """Two CPV codes in the SAME division on one notice must count the notice
    once — not twice — in notice_count (and not skew the value/date aggregates)."""
    opp = _opp("UK:1", "Acme Ltd", estimated_value_eur=500_000, status="OPEN")
    session.add(opp); session.commit()
    resolve(session)
    # Both codes are division "72"; the notice should still count as 1.
    session.add(TenderCpv(tender_id=opp.id, cpv_code="72500000", cpv_division="72"))
    session.add(TenderCpv(tender_id=opp.id, cpv_code="72600000", cpv_division="72"))
    session.commit()

    rollup(session)
    stats = session.exec(BuyerCategoryStat.__table__.select()).fetchall()
    assert len(stats) == 1
    assert stats[0].notice_count == 1            # not 2 (deduped per notice)
    assert stats[0].avg_value_eur == 500_000     # value counted once, not averaged twice


# ── C5 score integration ──────────────────────────────────────────────────────

def test_score_buyer_none_neutral():
    from app.scoring.relevance import score_buyer
    assert score_buyer(None) == pytest.approx(0.5)


def test_score_buyer_zero():
    from app.scoring.relevance import score_buyer
    assert score_buyer(0) == 0.0


def test_score_buyer_occasional():
    from app.scoring.relevance import score_buyer
    assert score_buyer(1) == pytest.approx(0.5)
    assert score_buyer(2) == pytest.approx(0.5)


def test_score_buyer_regular():
    from app.scoring.relevance import score_buyer
    assert score_buyer(3) == pytest.approx(0.8)
    assert score_buyer(5) == pytest.approx(0.8)


def test_score_buyer_frequent():
    from app.scoring.relevance import score_buyer
    assert score_buyer(6) == pytest.approx(1.0)
    assert score_buyer(20) == pytest.approx(1.0)
