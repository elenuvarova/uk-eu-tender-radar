# UK & EU Procurement Radar — Data Model

*Single source of truth for the database schema. SQLModel/SQLAlchemy over SQLite (local) and Supabase Postgres (prod). Source-field mapping lives in [RESEARCH.md](./RESEARCH.md) §4; scoring fields in [RESEARCH.md](./RESEARCH.md) §5; API shapes in [API_CONTRACT.md](./API_CONTRACT.md). Other docs reference this file rather than restating it.*

## Entity overview

```
SupplierProfile ──< RelevanceScoreCache >── TenderOpportunity ──< TenderCpv
                                                   │
                                                   └── buyer_id ──> Buyer ──< BuyerCategoryStat
SavedSearch (standalone)            FxRate (reference)
```

- One `TenderOpportunity` per notice process, keyed `source + source_notice_id`.
- `TenderCpv` is a child table (one row per CPV code) so prefix/division filtering is index-friendly across both SQLite and Postgres.
- `Buyer` is the entity-resolution layer over inconsistent free-text buyer names; `TenderOpportunity.buyer_id` is nullable until resolution runs.
- `BuyerCategoryStat` is a pre-aggregated rollup (refreshed by a job) powering score component C5 and dashboards.
- `RelevanceScoreCache` is the join of a profile × a tender, invalidated on profile change or deadline day-rollover.

---

## Tables

### `TenderOpportunity` — the unified notice record
| Column | Type | Notes |
|---|---|---|
| `id` | str (PK) | `"UK:<ocid>"` / `"EU:<publication-number>"` |
| `source` | str | `UK` \| `EU` |
| `source_notice_id` | str | original notice id (ocid / publication-number) |
| `source_url` | str | link back to the official notice |
| `title` | str | chosen-language title |
| `title_lang` | str | language of `title` (esp. for TED multilingual) |
| `description` | str \| null | |
| `buyer_id` | FK→Buyer, null | populated by the resolution job |
| `buyer_name` | str \| null | raw, as published |
| `buyer_country` | str \| null | ISO code |
| `buyer_region_raw` | str \| null | region as published |
| `buyer_region_code` | str \| null | normalized NUTS (EU) / ITL (UK) where parseable |
| `estimated_value` | float \| null | original value — **frequently absent** |
| `currency` | str \| null | original currency (GBP/EUR/…) |
| `estimated_value_eur` | float \| null | derived from a dated FX snapshot |
| `fx_rate_date` | date \| null | FX snapshot date used |
| `publication_date` | datetime | |
| `deadline` | datetime \| null | tz-aware |
| `deadline_tz_offset` | str \| null | original offset retained (open/closed judged in local time) |
| `notice_type` | enum | `PLANNING\|TENDER\|AWARD\|CONTRACT\|MODIFICATION\|OTHER` |
| `procedure_type` | enum | `OPEN\|SELECTIVE\|LIMITED\|DIRECT\|OTHER` |
| `procedure_type_raw` | str \| null | source detail (OCDS `procurementMethodDetails` / eForms BT-105) |
| `status` | enum | `PLANNED\|OPEN\|CLOSED\|AWARDED\|UNSUCCESSFUL\|CANCELLED` |
| `award_supplier` | str \| null | only on award/result notices |
| `raw_json` | JSON | full original payload, for traceability/audit |
| `created_at` / `updated_at` | datetime | |

- **Indexes:** `deadline`, `buyer_country`, `source`, `estimated_value`, `status`.
- **Full-text:** `tsvector(title, description)` in Postgres; `LIKE` fallback in SQLite.
- Every field except identity fields (`id`, `source`, `source_notice_id`) is **nullable by design** — sources omit data routinely.

### `TenderCpv` — CPV child table (index-friendly filtering)
| Column | Type | Notes |
|---|---|---|
| `tender_id` | FK→TenderOpportunity | |
| `cpv_code` | str | 8-digit CPV |
| `cpv_division` | str | 2-digit division (for readable buckets) |

### `Buyer` — entity resolution over free-text names
| Column | Type | Notes |
|---|---|---|
| `id` | str (PK) | internal canonical id |
| `canonical_name` | str | resolved display name |
| `source_ids` | JSON | `{ ocds_id, ted_id, … }` from each source |
| `country` | str \| null | |
| `region` | str \| null | |
| `name_aliases` | JSON | raw `buyer_name` variants mapped here |

> ⚠️ Core data risk: free-text buyer names don't reconcile across (or within) sources and have no shared org id. Ship notice counts first; sharpen per-buyer stats as resolution matures.

### `BuyerCategoryStat` — pre-aggregated rollup
| Column | Type | Notes |
|---|---|---|
| `buyer_id` | FK→Buyer | |
| `cpv_division` | str | 2-digit |
| `notice_count` | int | |
| `awarded_count` | int | sparse (award notices are a minority) |
| `avg_value` / `sum_value` | float | |
| `value_currency` | str | |
| `last_notice_date` | date | |
| `window_start` / `window_end` | date | e.g. trailing 24 months |

Refreshed by a scheduled job (`jobs/buyer_rollup.py`), not per request. Powers score component **C5** and dashboard "top buyers / categories".

### `SupplierProfile` — the scoring "lens"
| Column | Type | Notes |
|---|---|---|
| `id` | str (PK) | `"default"` for the single MVP profile |
| `name` | str | |
| `target_cpv_codes` | JSON | e.g. `["72000000","48000000"]` |
| `keywords` | JSON | e.g. `["cloud migration","GDPR"]` |
| `value_min` / `value_max` | float | |
| `value_currency` | str | |
| `target_countries` | JSON | ISO codes; **hard pre-filter** in scoring |
| `min_days_to_bid` | int | default 7 |

### `SavedSearch`
| Column | Type | Notes |
|---|---|---|
| `id` | str (PK) | |
| `name` | str | |
| `filters_json` | JSON | the feed filter set |
| `alert_enabled` | bool | inert in MVP |
| `alert_frequency` | enum \| null | post-MVP |
| `last_run_at` | datetime \| null | |

### `RelevanceScoreCache`
| Column | Type | Notes |
|---|---|---|
| `profile_id` | FK→SupplierProfile | |
| `tender_id` | FK→TenderOpportunity | |
| `score` | int | 0–100 |
| `breakdown_json` | JSON | `{ sCPV, sKW, sVAL, sDDL, sBUY, reasons[] }` |
| `computed_at` | datetime | |
| `valid_until` | datetime | next local midnight (keeps the deadline component correct) |

### `FxRate` — reference table
| Column | Type | Notes |
|---|---|---|
| `base_currency` | str | |
| `quote_currency` | str | |
| `rate` | float | |
| `as_of_date` | date | values are point-in-time; store the rate + date used |

---

## Lifecycle & integrity notes
- **Releases per notice:** OCDS emits multiple releases (planning→tender→award) per `ocid`; collapse into the current state on `TenderOpportunity` while retaining the timeline in `raw_json`.
- **Dedup:** primary key `source + source_notice_id`. Cross-source secondary guard: fuzzy `(title, buyer_name, deadline, value)` — the two UK platforms use different ocid prefixes, so never dedupe on ocid alone.
- **Money:** never overwrite `estimated_value`/`currency`; the EUR figure is always derived and carries its `fx_rate_date`.
- **Synthetic status:** `CLOSED` = `OPEN` whose `deadline < now` (no source field for it).
- **Dialect parity:** JSON columns + the `TenderCpv` child table keep array/prefix queries working on both SQLite (local) and Postgres (prod), mirroring the `DATABASE_URL` switch.
