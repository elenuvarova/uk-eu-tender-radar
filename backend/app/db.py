# The dialect is picked from DATABASE_URL so the same config works locally
# (blank -> SQLite file) and on Render (DATABASE_URL -> Postgres).
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel, Session, create_engine

from app.config import settings

_url = settings.database_url

if _url.startswith("postgres://") or _url.startswith("postgresql://"):
    # SQLAlchemy 2.x + psycopg3 wants the postgresql+psycopg scheme.
    normalized = _url.replace("postgres://", "postgresql+psycopg://", 1).replace(
        "postgresql://", "postgresql+psycopg://", 1
    )
    db_kind = "postgres"
    # The Supabase transaction pooler (port 6543) routes each transaction to a
    # possibly-different backend, so:
    #  - prepare_threshold=0 disables server-side prepared statements, and
    #  - NullPool avoids reusing connections that may carry stale server state.
    connect_args = {"prepare_threshold": 0}
    if settings.is_production:
        connect_args["sslmode"] = "require"
    engine = create_engine(
        normalized, echo=False, poolclass=NullPool, connect_args=connect_args
    )
else:
    db_kind = "sqlite"
    engine = create_engine(
        f"sqlite:///{settings.sqlite_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )


def init_db() -> None:
    # Import models so they register on SQLModel.metadata before create_all.
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
