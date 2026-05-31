from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401  (register models on SQLModel.metadata)
from app.main import app
from app.db import get_session


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    # Fresh in-memory DB per test — isolated, never touches the dev SQLite file.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    # Reuse the session fixture's connection so rows added via `session` in a
    # test are visible to requests made through `client`, and vice-versa.
    def get_session_override() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
