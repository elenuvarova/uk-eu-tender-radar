# UK & EU Procurement Radar

A cross-border public-procurement intelligence tool for small digital/edtech suppliers. It ingests open **UK (Find a Tender / OCDS)** and **EU (TED / eForms)** notices, normalizes them into one unified model, scores relevance, and surfaces matching opportunities. Uses SQLite locally (nothing to install) and PostgreSQL in production, picking the dialect automatically from `DATABASE_URL`. Deploys free on [Render](https://render.com).

> **Status:** early build. Phase 0 (FastAPI backend scaffold + unified data model) is in place; ingestion, scoring, and dashboard land in later phases. See [docs/](docs/) for the full plan.

## Stack

- **Frontend:** React 18 + Vite 5 (JavaScript/JSX)
- **Backend:** Python + FastAPI + SQLModel
- **Database:** SQLite for local dev, PostgreSQL in production — selected at startup from `DATABASE_URL`
- **Ingestion:** Python (httpx) — UK Find a Tender (OCDS) + EU TED (eForms)
- **Deploy:** Render free tier (free web service + free Postgres) via `render.yaml` Blueprint
- **Docker:** used only by Render's build — local dev needs no Docker

## Documentation

All planning docs live in [docs/](docs/): [research](docs/RESEARCH.md), [dev plan](docs/DEV_PLAN.md), [data model](docs/DATA_MODEL.md), [API contract](docs/API_CONTRACT.md), [spike findings](docs/SPIKE_FINDINGS.md), [glossary](docs/GLOSSARY.md), and the [portfolio case study](docs/portfolio/CASE_STUDY.md).

## Project structure

```
.
├── backend/              FastAPI app (app/), Alembic migrations, tests
│   ├── app/
│   │   ├── main.py       FastAPI app + prod static serving
│   │   ├── config.py     env settings (DATABASE_URL switch)
│   │   ├── db.py         engine/session (sqlite | postgres)
│   │   ├── models/       SQLModel tables
│   │   └── api/          routers (health; more in later phases)
│   ├── alembic/          migrations
│   ├── tests/            pytest + real FTS/TED fixtures
│   └── pyproject.toml
├── frontend/             React + Vite
├── docs/                 research, plan, data model, API contract
├── Dockerfile            Render build (Node frontend → Python runtime)
├── render.yaml
└── .env.example
```

## Local development

No database to install — SQLite is built in; the backend creates `data.sqlite` on first run. Open two terminals:

**Terminal 1 — backend**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 3001
```

**Terminal 2 — frontend**
```bash
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173**. The Vite dev server proxies `/api` requests to the backend on port 3001.

## Deploy to Render

1. Push this repo to GitHub.
2. In Render, click **New → Blueprint** and connect your repo.
3. Render reads `render.yaml`, provisions a free Postgres database and a free Docker web service, and wires `DATABASE_URL` automatically — no connection string to copy/paste.

Notes on the free tier:
- The free web service **sleeps after inactivity**, so the first request after idle has a ~30s cold start.
- Render's **free Postgres expires after 30 days**.

## Endpoints

- `GET /api/health` — checks the database connection, returns `{ "status": "ok", "db": "sqlite" | "postgres" }`
- `GET /api/hello` — returns `{ "message": "Hello from the backend 👋" }`
- `GET *` (production only) — serves the built frontend

## Attribution

Built on open data: UK Find a Tender (Open Government Licence v3.0) and EU TED (© European Union, reused under Commission Decision 2011/833/EU).
