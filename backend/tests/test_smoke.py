from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] in ("sqlite", "postgres")


def test_hello():
    r = client.get("/api/hello")
    assert r.status_code == 200
    assert r.json() == {"message": "Hello from the backend 👋"}


def test_models_registered():
    from sqlmodel import SQLModel
    import app.models  # noqa: F401

    tables = set(SQLModel.metadata.tables)
    assert {"tender_opportunity", "tender_cpv"} <= tables


def test_fixtures_present():
    from pathlib import Path

    fx = Path(__file__).parent / "fixtures"
    assert (fx / "fts_release_package.json").exists()
    assert (fx / "ted_search.json").exists()
