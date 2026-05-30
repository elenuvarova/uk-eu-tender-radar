# UK & EU Procurement Radar — API Contract

*Draft REST contract between the React frontend and the FastAPI backend. Lets both sides build in parallel. Aligns to the schema in [DATA_MODEL.md](./DATA_MODEL.md) and the scoring in [RESEARCH.md](./RESEARCH.md) §5. Versioned under `/api`; all responses JSON; all dates ISO-8601.*

## Conventions

- Base path: `/api`. In production the FastAPI app also serves the built frontend (catch-all → `index.html`).
- **Pagination:** cursor-style — `?limit=` (default 25, max 100) + `?cursor=` (opaque). Responses return `{ items, next_cursor }`; `next_cursor: null` = last page.
- **Errors:** `{ "error": { "code": "STRING_CODE", "message": "human readable" } }` with appropriate HTTP status (400 validation, 404 not found, 422 unprocessable, 500 server).
- **No auth in the MVP.** A single implicit `SupplierProfile` is used; real auth is post-MVP. Endpoints are written so an `Authorization` header can be added later without shape changes.
- **Money:** every value field returns both the original (`estimated_value` + `currency`) and the normalized `estimated_value_eur` (nullable). Clients should display "Value not disclosed" when null.

---

## Endpoints

### Opportunities

**`GET /api/opportunities`** — the unified, filterable feed.

Query params (all optional, combine with AND):
| Param | Type | Notes |
|---|---|---|
| `source` | `UK` \| `EU` | omit = both |
| `country` | ISO code, repeatable | buyer country |
| `cpv` | string, repeatable | prefix match (e.g. `48`, `72`, `80420000`) |
| `q` | string | full-text over title + description |
| `deadline_from` / `deadline_to` | date | |
| `value_min` / `value_max` | number (EUR) | filters on `estimated_value_eur` |
| `include_unspecified_value` | bool (default `true`) | keep notices with no value when value filter set |
| `notice_type` | enum, repeatable | `PLANNING\|TENDER\|AWARD\|CONTRACT\|MODIFICATION\|OTHER` |
| `status` | enum, repeatable | `PLANNED\|OPEN\|CLOSED\|AWARDED\|UNSUCCESSFUL\|CANCELLED` |
| `sort` | enum | `deadline_asc` (default) \| `published_desc` \| `value_desc` \| `relevance_desc`* |
| `profile_id` | string | required when `sort=relevance_desc`; attaches scores |
| `limit` / `cursor` | | pagination |

\* `relevance_desc` requires `profile_id`; each item then includes `relevance`.

Response:
```json
{
  "items": [
    {
      "id": "UK:ocds-h6vhtk-049a1b",
      "source": "UK",
      "source_url": "https://www.find-tender.service.gov.uk/Notice/049a1b-2026",
      "title": "Cloud Migration and Data Centre Consolidation",
      "title_lang": "en",
      "buyer_name": "Example County Council",
      "buyer_country": "GB",
      "buyer_region_code": "UKG31",
      "cpv_codes": ["72500000", "72100000"],
      "estimated_value": 850000, "currency": "GBP", "estimated_value_eur": 1003000,
      "publication_date": "2026-05-20T09:00:00Z",
      "deadline": "2026-06-20T17:00:00+01:00",
      "notice_type": "TENDER",
      "procedure_type": "OPEN",
      "status": "OPEN",
      "relevance": { "score": 72, "reasons": [
        {"factor": "keyword", "ok": true,  "text": "matched \"cloud migration\" in the title"},
        {"factor": "cpv",     "ok": false, "text": "only a broad division-level CPV match (72 — IT services)"}
      ] }
    }
  ],
  "next_cursor": "eyJvZmZzZXQiOjI1fQ=="
}
```

**`GET /api/opportunities/{id}`** — full detail for one notice (all fields incl. `description`, `award_supplier`; optionally `?profile_id=` to attach `relevance`). `404` if unknown.

**`GET /api/facets`** — counts for building filter UI and dashboards. Accepts the same filters as the feed; returns aggregates rather than rows:
```json
{
  "total": 1320,
  "by_country": [{"country": "GB", "count": 420}, {"country": "DE", "count": 64}],
  "by_source": {"UK": 612, "EU": 708},
  "by_cpv_division": [{"division": "72", "label": "IT services", "count": 540}],
  "closing_soon": 88,
  "top_buyers": [{"buyer_id": "b_123", "name": "Example County Council", "count": 31}]
}
```

### Buyers

**`GET /api/buyers/{buyer_id}`** — buyer profile (best-effort; depends on entity resolution).
```json
{
  "id": "b_123", "canonical_name": "Example County Council",
  "country": "GB", "region": "UKG31",
  "notice_count": 31, "awarded_count": 7,
  "avg_value_eur": 640000,
  "top_categories": [{"cpv_division": "72", "label": "IT services", "count": 18}],
  "recent_notices": [{"id": "UK:ocds-...", "title": "...", "publication_date": "..."}],
  "known_suppliers": ["Acme Digital Ltd"]
}
```
Note: `awarded_count`, `known_suppliers` are sparse (award data is a minority of notices) — clients show "best-effort / incomplete".

### Supplier profile (the scoring lens)

**`GET /api/profile`** · **`PUT /api/profile`** — the single MVP profile.
```json
{
  "id": "default",
  "name": "My company",
  "target_cpv_codes": ["72000000", "48000000"],
  "keywords": ["cloud migration", "GDPR", "data centre"],
  "value_min": 200000, "value_max": 2000000, "value_currency": "GBP",
  "target_countries": ["GB", "IE", "DE"],
  "min_days_to_bid": 7
}
```
`PUT` validates and recomputes/invalidates the relevance cache.

### Saved searches

**`GET /api/saved-searches`** · **`POST /api/saved-searches`** · **`DELETE /api/saved-searches/{id}`**
```json
{ "id": "ss_1", "name": "Digital learning UK+BE+NL",
  "filters": { "source": null, "countries": ["GB","BE","NL"],
               "cpv": ["80420000","48000000"], "q": "learning" } }
```
(Alerting is post-MVP; the `alert_enabled`/`alert_frequency` fields exist but are inert in the MVP.)

### Dashboard

Dashboard widgets are powered by **`GET /api/facets`** (above) plus:

**`GET /api/dashboard/uk-vs-eu`** — directional comparison (count-weighted by default; value-weighted via `?weight=value`, flagged as approximate due to GBP/EUR + threshold differences).
```json
{ "by_category": [
    {"cpv_division": "72", "label": "IT services", "uk": 210, "eu": 330}
  ],
  "weight": "count",
  "note": "Value comparisons are directional only — GBP/EUR and differing thresholds." }
```

### System

**`GET /api/health`** → `{ "status": "ok", "db": "sqlite" | "postgres" }` (parity with the existing template).
**`GET /api/meta`** → ingestion freshness: `{ "last_ingest": {"UK": "...", "EU": "..."}, "counts": {"UK": 612, "EU": 708} }`.

---

## Build order alignment

| Phase (DEV_PLAN §4) | Endpoints unlocked |
|---|---|
| 1 — UK spike | (internal ingestion only) |
| 2 — EU spike | (internal ingestion only) |
| 3 — Unified dashboard | `GET /opportunities`, `/opportunities/{id}`, `/facets`, `/dashboard/uk-vs-eu`, `/meta`, `/health` |
| 4 — Scoring | `GET/PUT /profile`, `relevance` on feed, `sort=relevance_desc`, `/saved-searches` |
| 5 — Buyer intelligence | `GET /buyers/{id}`, `top_buyers` in facets |

## Open questions (resolve during build)
- Cursor encoding: keyset (on `deadline`+`id`) vs offset — prefer keyset for stable paging.
- Whether `relevance` is computed inline or read from `RelevanceScoreCache` on the feed (cache, with `valid_until = next local midnight`).
- Rate-limit/quotas on the public API surface (likely unnecessary for the MVP single-user demo).
