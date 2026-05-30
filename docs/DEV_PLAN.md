# UK & EU Procurement Radar — Development Plan

*Stack decision: **Full Python (FastAPI)**. Companion to [RESEARCH.md](./RESEARCH.md) and [portfolio/CASE_STUDY.md](./portfolio/CASE_STUDY.md). Name kept as "UK & EU Procurement Radar" for the portfolio build.*

> ⚠️ **Repo note:** this repository currently holds a **Node/Express/Sequelize** full-stack template. The FastAPI decision means the backend is **replaced**, not extended. The React+Vite frontend and the Render/Docker deploy scaffolding are reusable; `backend/` will be rebuilt in Python. See §8 for the migration step.

---

## 1. Target architecture

```
                         ┌────────────────────────┐
                         │  React + Vite + Tailwind│   (reuse existing frontend/, add Tailwind+shadcn)
                         │   feed · filters · cards │
                         │  dashboard · charts      │
                         └───────────┬────────────┘
                                     │ HTTP /api
                         ┌───────────▼────────────┐
                         │   FastAPI (Python)      │   read API: opportunities, scoring,
                         │   SQLModel + Pydantic   │   buyers, dashboards, saved searches
                         └───────────┬────────────┘
                                     │ SQLAlchemy
                         ┌───────────▼────────────┐
                         │  PostgreSQL (Supabase)  │   prod; SQLite for local dev
                         └───────────▲────────────┘
                                     │ writes
            ┌────────────────────────┴───────────────────────┐
            │   Python ingestion + normalization workers      │
            │   httpx · pandas · OCDS/eForms mappers          │
            └───────┬─────────────────────────────┬──────────┘
                    │                              │
        ┌───────────▼──────────┐      ┌────────────▼─────────┐
        │ Find a Tender OCDS API│      │   TED API v3 (search) │
        │ (anonymous, cursor)   │      │  (anonymous, scroll)  │
        └───────────────────────┘      └───────────────────────┘

   Scheduler: GitHub Actions cron (MVP) → Render Cron later
```

### Stack
| Layer | Choice | Notes |
|---|---|---|
| Frontend | React 18 + Vite 5 + Tailwind + shadcn/ui + Recharts | Reuse existing `frontend/`; add Tailwind/shadcn |
| API | **FastAPI** + Uvicorn | Pydantic v2 response models |
| ORM | **SQLModel** (SQLAlchemy core) | SQLite local, Postgres prod — mirror the template's `DATABASE_URL` switch |
| DB | Supabase Postgres (prod) / SQLite (local) | No DB to install locally |
| Ingestion | httpx (async), pandas | OCDS + eForms→unified mappers |
| Migrations | Alembic | |
| Scheduler | GitHub Actions cron (MVP) | manual `refresh` command first; Render Cron later |
| Deploy | Render web service (API serves built frontend) + Supabase | reuse `render.yaml`/`Dockerfile`, rewrite for Python |
| Tests | pytest | mapper unit tests are the highest-value tests |

### Proposed repo layout (after migration)
```
backend/
  app/
    main.py              # FastAPI app, router mounting, static serving
    config.py            # env: DATABASE_URL switch (sqlite/postgres)
    db.py                # engine/session (SQLModel)
    models/              # SQLModel tables (see DATA_MODEL.md)
    schemas/             # Pydantic response models
    api/                 # routers: opportunities, buyers, dashboard, profiles, searches
    ingestion/
      fts.py             # UK Find a Tender OCDS client + harvester
      ted.py             # EU TED v3 client + harvester
      normalize/
        ocds.py          # OCDS → TenderOpportunity
        eforms.py        # eForms → (OCDS-shaped) → TenderOpportunity
        enums.py         # common enum mappers
        cpv.py           # CPV include-list + prefix matching
      run.py             # CLI: `python -m app.ingestion.run --source fts --since ...`
    scoring/
      relevance.py       # the 0–100 rule-based score (RESEARCH.md §5)
      weights.py         # SCORE_WEIGHTS config
    jobs/
      buyer_rollup.py    # BuyerCategoryStat aggregation
      fx.py              # FX snapshot fetch
  alembic/
  tests/
  pyproject.toml
frontend/                # existing React+Vite (add Tailwind/shadcn)
docs/                    # RESEARCH.md, DEV_PLAN.md, portfolio/
.github/workflows/ingest.yml
render.yaml  Dockerfile  .env.example
```

---

## 2. MVP scope (niche: digital / edtech / software services)

**In scope:** unified UK+EU feed · filters (country, source, CPV, keyword, deadline, value, notice type) · tender card · rule-based relevance score with reasons · buyer profile (best-effort) · dashboard (by country, closing soon, top buyers, top categories) · saved search profiles.

**Out of scope (post-MVP):** RAG / LLM features, bid writing, CRM, document Q&A, email alerts, auth/multi-tenant (single implicit profile for MVP, real auth later).

---

## 3. Data model

The full SQLModel schema (all tables, columns, types, indexes, relationships, and lifecycle/integrity notes) is the **single source of truth** in [DATA_MODEL.md](./DATA_MODEL.md).

Tables at a glance: `TenderOpportunity` (the unified record) · `TenderCpv` (CPV child for prefix filtering) · `Buyer` (entity resolution) · `BuyerCategoryStat` (rollup powering score C5 + dashboards) · `SupplierProfile` (the scoring lens) · `SavedSearch` · `RelevanceScoreCache` · `FxRate`.

---

## 4. Phased build (each phase ships something usable)

### Phase 0 — Foundation & migration *(prep)*
- Replace Node backend with FastAPI skeleton; keep `DATABASE_URL` sqlite/postgres switch.
- SQLModel `TenderOpportunity` + `TenderCpv`; Alembic baseline.
- `/api/health` parity; wire frontend to FastAPI; add Tailwind+shadcn.
- **Run the RESEARCH.md §9 verification checklist** against live APIs first.
- *Done when:* FastAPI boots on SQLite, frontend talks to it, one verification sample saved.

### Phase 1 — UK spike (FTS) *(prove the model on one source)*
- `ingestion/fts.py`: cursor-paginated OCDS harvester (follow `links.next`, ISO datetime, back off on 429).
- `normalize/ocds.py`: OCDS → `TenderOpportunity` (resolve `parties[]`, read both CPV paths, handle award-vs-tender stage nulls).
- CPV niche filter (Tier 1/2/3). CLI: pull ~100 digital/edtech UK notices.
- pytest mapper tests on saved fixtures.
- *Done when:* ~100 real UK notices queryable in the unified model with correct CPV/value/deadline.

### Phase 2 — EU spike (TED) *(prove unified model on a 2nd format)*
- `ingestion/ted.py`: anonymous `POST /v3/notices/search`, `ITERATION` pagination, tight `fields`, expert query with CPV + country + date.
- `normalize/eforms.py`: eForms → unified (lang `eng` selection + fallback, dedupe flattened arrays, coalesce procedure→lot, NUTS region, alpha-3 country).
- Common enum mappers; FX snapshot for EUR↔GBP (`jobs/fx.py`).
- *Done when:* ~100 EU notices land in the **same** model alongside UK; English titles resolved; values normalized to EUR.

### Phase 3 — Unified dashboard *(the product surface)*
- Read API: `GET /api/opportunities` with filters (country, source, CPV prefix, keyword/FTS, deadline, value+include-nulls toggle, notice_type), pagination, sort.
- Frontend: feed table, tender card, filter panel, dashboard (by country, closing soon, top buyers, top categories via Recharts), UK-vs-EU comparison (directional, count-weighted default).
- *Done when:* a user can browse + filter UK and EU tenders together and read dashboards.

### Phase 4 — Relevance scoring *(the differentiator)*
- `scoring/relevance.py` (RESEARCH.md §5): 5 components, `SCORE_WEIGHTS` config, reason bullets.
- `SupplierProfile` CRUD; `RelevanceScoreCache` with midnight `valid_until`.
- Frontend: profile form, score badge + "X% relevant because…" reasons, sort-by-relevance.
- *Done when:* opportunities rank against a saved profile with visible, auditable reasons.

### Phase 5 — Buyer intelligence *(depth)*
- `Buyer` entity resolution (normalize/fuzzy-match free-text names; populate `buyer_id`).
- `jobs/buyer_rollup.py` → `BuyerCategoryStat`; activates score component C5.
- Buyer profile page: notices, top categories, avg value, award history (best-effort), known suppliers.
- *Done when:* buyer pages render and C5 contributes to scores.

### Phase 6 — AI / RAG *(post-MVP, later)*
- Summarize tender requirements; bid/no-bid reasoning with citations; ask-the-notice Q&A; profile-vs-tender fit.
- Embeddings over `description` + documents; retrieval with citations. Built with the latest Claude models; keep rule-based score as the explainable baseline.
- *Done when:* (deferred — separate initiative once structured layer is solid).

---

## 5. Scheduling & ops
- **MVP:** manual `python -m app.ingestion.run` + a GitHub Actions cron (daily incremental: FTS `updatedFrom=yesterday`, TED `scope=ACTIVE` / `publication-date>=yesterday`).
- **Caching/politeness:** serialize requests, exponential back-off on 429, cache raw payloads in `raw_json`. Respect TED ~700 req/min and FTS undocumented limits.
- **No VDS needed** for MVP (confirmed in brief) — Render + Supabase + GH Actions cover it. VDS only later for heavy PDF/OCR, browser automation, or vector DB.

## 6. Compliance (build into the app)
- Attribution footer: OGL v3.0 (UK) + "© European Union, ted.europa.eu" (EU). Attributions page.
- No crests/EU logos. Treat named contacts as personal data — minimise, don't surface/re-broker.
- Rate-limit respect + caching.

## 7. Testing priorities
1. **Mapper unit tests** (OCDS + eForms → unified) on saved real fixtures — highest value, catches schema drift.
2. CPV prefix-matching + include-list tests.
3. Scoring component tests (each sub-score tier + worked example from RESEARCH.md §5).
4. API contract tests on `/api/opportunities` filters.

## 8. Migration step (Node → Python)
The current `backend/` (Express+Sequelize) is replaced. Reusable as reference for: the `DATABASE_URL` dialect switch pattern, the prod-serves-frontend approach, and `render.yaml`/`Dockerfile` structure (rewrite for Python/uvicorn). Frontend and docs are kept. Recommend doing this in Phase 0 on a branch.

## 9. Top risks (from research)
| Risk | Mitigation |
|---|---|
| Missing `estimated_value` (30–50%) | nullable everywhere; value filter "include unspecified" toggle; score null=0.5 neutral |
| Buyer entity resolution (names don't reconcile) | dedicated `Buyer` layer + fuzzy match; ship counts first, sharpen async |
| eForms lot-centric + flattened arrays | coalesce procedure→lot; dedupe arrays in mapper |
| Unverified field paths (§9 checklist) | confirm against one real sample in Phase 0 before coding mappers |
| Name collision (TenderRadar) | accepted for portfolio; revisit before public launch |
| GBP/EUR comparison distortion | dated FX snapshots; frame UK-vs-EU value as directional |
| API rate limits | serialize + back-off + cache |
