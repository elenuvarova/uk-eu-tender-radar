# Backend — UK & EU Procurement Radar (FastAPI)

Python + FastAPI + SQLModel. SQLite locally (nothing to install), Postgres in production — selected from `DATABASE_URL` (see [app/db.py](app/db.py)).

## Local development

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env          # optional; defaults work
uvicorn app.main:app --reload --port 3001
```

- `GET http://localhost:3001/api/health` → `{"status":"ok","db":"sqlite"}`
- `GET http://localhost:3001/api/hello`

A `data.sqlite` file is created on first run.

## Migrations (Alembic)

```bash
alembic revision --autogenerate -m "message"
alembic upgrade head
```

`init_db()` also runs `create_all` on startup for fast local iteration; Alembic is the source of truth for schema changes going forward.

## Tests

```bash
pytest
```

## Layout

```
app/
  main.py            FastAPI app + prod static serving
  config.py          env settings (DATABASE_URL switch)
  db.py              engine/session, sqlite|postgres
  models/            SQLModel tables (see ../docs/DATA_MODEL.md)
  api/               routers (health; opportunities/buyers/... in later phases)
  ingestion/         FTS + TED clients + normalize/ (Phases 1-2)
  scoring/           relevance score (Phase 4)
  jobs/              buyer rollup, FX (Phase 5/2)
alembic/             migrations
tests/               pytest + fixtures/ (real FTS+TED samples)
```
