import os
os.environ.setdefault("ENV", "test")

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

from app.main import app
from app.db import engine as app_engine
from app.db import get_session

import app.models  # noqa: F401  (register models on SQLModel.metadata)


@pytest.fixture
def session():
    SQLModel.metadata.create_all(app_engine)
    s = Session(app_engine)
    try:
        yield s
    finally:
        # Close before drop_all, else SQLite holds the connection and
        # drop_all raises "database table is locked".
        s.close()
        SQLModel.metadata.drop_all(app_engine)


@pytest.fixture
def client():
    SQLModel.metadata.create_all(app_engine)

    def _override():
        s = Session(app_engine)
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(app_engine)
