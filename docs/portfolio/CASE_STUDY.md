# UK & EU Procurement Radar

A cross-border public-procurement intelligence tool that ingests open UK (Find a Tender / OCDS) and EU (TED) notices, normalizes them into one unified data model, scores their relevance, and helps small digital/edtech suppliers find public-sector opportunities they would otherwise miss.

- Live demo: TODO (add link once deployed)
- Repository: TODO (add link)

> Status: portfolio case study. Sections marked **TODO** are placeholders for real metrics, screenshots, code links, and final decisions captured during the build. Nothing in those sections is invented or final yet.

---

## TL;DR

- **What it is** — A tool that pulls public-sector tender notices from the UK and EU into one searchable feed, normalizes the very different source formats, and ranks each opportunity by how relevant it is to a given supplier.
- **Who it's for** — Small digital and edtech suppliers who want to sell to government but lack a bid team to monitor multiple national portals by hand.
- **The hard part** — Two structurally different open-data standards (UK OCDS JSON vs EU TED eForms), multiple languages, and inconsistent / missing fields all have to collapse into one coherent, queryable model — without losing meaning.
- **The outcome** — TODO (add measured results: notices ingested, source coverage, scoring precision, time-to-first-relevant-result, user feedback).

---

## The problem

Public bodies across the UK and EU publish thousands of tender notices, and the data is open. In principle a small supplier can find every relevant contract. In practice they rarely do.

- **Fragmentation.** UK notices live on Find a Tender (and predecessor systems); EU notices live on TED. Separate portals, separate search interfaces, separate formats, separate quirks.
- **Format heterogeneity.** The UK publishes structured data via OCDS (Open Contracting Data Standard); the EU publishes via TED using eForms. The same real-world concept — "what is being bought, by whom, for how much, by when" — is expressed differently in each.
- **Language.** EU notices appear in many languages. A supplier searching English keywords misses relevant non-English notices entirely.
- **Noise vs signal.** Most published notices are irrelevant to any single supplier. Manual filtering is slow, and naive keyword search either floods the user or silently drops good matches.
- **Missing and inconsistent fields.** Real notices omit values, use inconsistent classifications, and vary in completeness, which breaks simple filters.

Cross-border is hard precisely because solving it well means reconciling all of the above at once: you cannot just merge two feeds, you have to make them mean the same thing.

---

## Target user & jobs-to-be-done

**Primary user:** a founder, BD lead, or solo operator at a small digital or edtech supplier (roughly 1–50 people) that wants public-sector revenue but has no dedicated bid/capture team.

Jobs-to-be-done:

- *When* a new public-sector opportunity appears in my space, *I want to* learn about it early, *so I can* decide whether to pursue it before the deadline.
- *When* I scan opportunities, *I want to* see only the ones genuinely relevant to what I sell, *so I can* avoid wasting hours filtering noise.
- *When* a tender looks relevant, *I want to* see the essentials at a glance (buyer, value, deadline, scope), *so I can* triage fast.
- *When* I find a promising notice, *I want to* get to the official source, *so I can* read the full documents and start a bid.

Out of scope for the MVP: bid writing, document management, and CRM. The tool's job is discovery and triage, not delivery.

---

## Why this is interesting technically

The core engineering challenge is **collapsing two heterogeneous open-data standards into one model without distorting either.**

- **UK Find a Tender** publishes via **OCDS** — a JSON contracting standard organized around a release/tender/award lifecycle.
- **EU TED** publishes via **eForms** — a different schema, multilingual, with its own field names, code lists, and structure.

The same business concept lands in different shapes, names, code lists, and languages across the two. The interesting work is the **normalization layer**: a mapping from each source format into a single `TenderOpportunity` model that is honest about what each source does and does not provide, handles missing fields gracefully, and stays explainable so a user can trust why something surfaced.

This is a real data-engineering problem wrapped in a real product problem — exactly the kind of thing that benefits from clear modeling decisions before any clever scoring.

---

## Data sources

Both sources were verified by live anonymous API calls during research (full detail in [RESEARCH.md](../RESEARCH.md) §2–3). A handful of field paths remain to be confirmed against a real sample before the mappers are written (RESEARCH.md §9).

- **UK — Find a Tender Service (FTS).** Publishes contract notices as open data using **OCDS 1.1** (Open Contracting Data Standard). Anonymous `GET /api/1.0/ocdsReleasePackages` with cursor pagination (`links.next`); near-real-time; **Open Government Licence v3.0**.
- **EU — TED (Tenders Electronic Daily).** Publishes notices using **eForms**, multilingual. Anonymous `POST /v3/notices/search` with an expert query language and scroll pagination; English available per notice; reusable under **Commission Decision 2011/833/EU**.

Both are **open data with anonymous read access** for published notices — **no API key** needed for the MVP's access pattern (search/incremental harvest). Keys are only required to *publish* unpublished notices, which this project never does.

---

## Architecture

> TODO: add architecture diagram.

```
[Schedulers] --> [Ingestion workers] --> [Normalization] --> [Database]
                                                                  |
                                                                  v
                                              [API] <----> [Frontend dashboard]
                                                |
                                                v
                                        [Relevance scoring]
```

Component list:

- **Frontend** — React + Vite dashboard for search, filtering, and triage of opportunities. (Lives in `frontend/`.)
- **API** — FastAPI (Python) service exposing normalized opportunities and scoring results to the frontend. (Lives in `backend/`.)
- **Ingestion** — Python workers (httpx + pandas) that fetch notices from Find a Tender (OCDS) and TED (eForms) and hand them to normalization.
- **Normalization** — maps each source format into the unified `TenderOpportunity` model via OCDS as a common intermediate representation.
- **Database** — SQLModel/SQLAlchemy over SQLite locally and Supabase Postgres in production (via `DATABASE_URL`).
- **Scheduler** — triggers periodic incremental ingestion (GitHub Actions cron for the MVP → Render Cron later).

The repo is a two-app layout (`frontend/` and `backend/`) with a `Dockerfile` and a `render.yaml`, so it deploys on Render; environment is configured via `.env` (see `.env.example`). In local dev frontend and backend run separately; in production the FastAPI app serves the built frontend. The current `Dockerfile`/`render.yaml` target the original Node template and are rewritten for Python/uvicorn during the backend migration ([DEV_PLAN.md](../DEV_PLAN.md) §8).

---

## The unified data model

Every notice, regardless of source, is normalized into a single `TenderOpportunity` shape. The illustrative shape below shows the core fields; the canonical, full schema (with the buyer-resolution, scoring-cache, and FX tables) lives in [DATA_MODEL.md](../DATA_MODEL.md), and the field-by-field source mapping in [RESEARCH.md](../RESEARCH.md) §4.

```python
# Core fields (SQLModel). Full model + supporting tables in DATA_MODEL.md.
class TenderOpportunity(SQLModel, table=True):
    id: str                       # "UK:<ocid>" / "EU:<publication-number>"
    source: str                   # "UK" | "EU"
    source_notice_id: str
    source_url: str

    title: str
    title_lang: str               # chosen language (esp. for TED multilingual)
    description: str | None

    buyer_name: str | None
    buyer_country: str | None     # ISO code
    buyer_region_code: str | None # NUTS (EU) / ITL (UK)

    cpv_codes: list[str]          # via TenderCpv child table for indexed prefix filtering
    estimated_value: float | None # frequently absent — nullable by design
    currency: str | None
    estimated_value_eur: float | None  # derived from a dated FX snapshot

    publication_date: datetime
    deadline: datetime | None     # tz-aware; original offset retained

    notice_type: str              # PLANNING | TENDER | AWARD | CONTRACT | MODIFICATION | OTHER
    procedure_type: str           # OPEN | SELECTIVE | LIMITED | DIRECT | OTHER
    status: str                   # PLANNED | OPEN | CLOSED | AWARDED | UNSUCCESSFUL | CANCELLED
    award_supplier: str | None

    raw_json: dict                # original payload retained for traceability
```

**The normalization challenge.** OCDS and eForms name and structure the same concepts differently, use different code lists, and vary in completeness. The approach is to use **OCDS as a common intermediate representation**: UK data is already OCDS; EU eForms is converted into an OCDS-shaped record, then both map into `TenderOpportunity`. Mapping means deciding, field by field, what is genuinely equivalent, what must be optional, and what to do when a source omits a value — plus three recurring landmines: missing contract values (30–50% of notices), multilingual EU titles (pick English, fall back to the official language), and buyer names that don't reconcile across sources (a dedicated entity-resolution layer). Retaining `raw_json` keeps every record traceable back to its origin, so mapping decisions can be audited and corrected.

---

## Key product decisions

- **Niche focus first (digital / edtech).** Rather than serving every sector, the MVP targets a single supplier niche. A narrow focus makes relevance scoring tractable and the value obvious to a specific user, instead of being a generic tender mirror.
- **Rule-based scoring before RAG.** Start with explainable, deterministic rules (keywords, CPV codes, country, value bands) before reaching for embeddings or LLM-based retrieval. Rules are debuggable, cheap, and let the user understand *why* something surfaced — trust first, sophistication later.
- **Tight MVP scope.** Discovery and triage only. No bid writing, no CRM, no document handling. The smallest thing that gets a user to "here are opportunities worth my attention."

---

## Relevance scoring

The MVP uses an **explainable, rule-based** score (0–100) against a supplier profile — no ML, so every result is auditable. Country is a hard pre-filter; the score is a weighted sum of five components (full formula + worked example in [RESEARCH.md](../RESEARCH.md) §5):

| Component | Weight | Signal |
|---|---:|---|
| CPV match | 35% | longest shared CPV prefix (exact > class > group > division) — the dominant lever |
| Keyword match | 25% | profile keywords in title (weighted) / description |
| Value in range | 15% | contract value within the supplier's band (missing value = neutral) |
| Days-to-deadline | 15% | enough time to bid; penalize too-soon and expired |
| Buyer repeat behaviour | 10% | buyer has posted similar-category notices before |

Each sub-score maps to a tier that auto-generates a reason bullet, so the UI can show *"72% relevant because…"* with ✅/⚠️ lines a supplier can trust. Weights live in a config object for later tuning.

TODO: validate weights against real data and decide the threshold for "worth showing."

---

## Challenges & how I solved them

> TODO: fill in with concrete examples, before/after, and code links once built. Placeholders below frame the expected problems.

- **Data normalization (OCDS vs eForms).** Reconciling two schemas into one model. TODO: document the mapping table and the hardest field-level decisions.
- **Multilingual notices (TED).** Handling non-English notices so they stay discoverable. TODO: document the approach (e.g., language detection, translated fields, or language-aware matching).
- **Missing / inconsistent fields.** Notices omit values or use inconsistent classifications. TODO: document defaults, optionality, and how missing data affects scoring and filtering.
- **Deduplication.** The same opportunity can appear more than once or be updated over time. TODO: document the dedup/merge strategy and the key used to identify "the same" notice.

---

## What I built (MVP)

> TODO: add screenshots for each feature.

- Unified opportunity feed combining UK and EU notices.
- Search and filtering. TODO: confirm final filters (keyword, country, CPV, value, deadline).
- Per-opportunity detail view with the essentials (buyer, value, deadline, scope) and a link to the official source.
- Relevance score with visible reasons.
- Scheduled ingestion keeping the feed current.

TODO: confirm the exact feature set that shipped in the MVP.

---

## Results & learnings

> TODO: this section is intentionally empty of numbers until measured. Do not fill with estimates.

- **Metrics** — TODO (e.g., notices ingested, source coverage, scoring precision/recall on a labeled sample, time-to-first-relevant-result).
- **What worked** — TODO.
- **What I'd do differently** — TODO.
- **RAG roadmap** — TODO: where semantic retrieval / LLM scoring would replace or augment the rule-based layer, and what evidence would justify the added cost and reduced explainability.

---

## Tech stack

- **Frontend:** React 18 + Vite 5 + Tailwind + shadcn/ui + Recharts.
- **Backend:** FastAPI (Python) + Uvicorn.
- **ORM / DB:** SQLModel/SQLAlchemy over SQLite (local) and Supabase Postgres (production, via `DATABASE_URL`); Alembic migrations.
- **Ingestion:** Python (httpx, pandas); OCDS + eForms mappers.
- **Scheduling:** GitHub Actions cron (MVP) → Render Cron later.
- **Containerization / hosting:** Render web service (API serves built frontend) + Supabase; `Dockerfile` + `render.yaml`.
- *(The repo began as a Node/Express/Sequelize template; the backend was migrated to FastAPI — see [DEV_PLAN.md](../DEV_PLAN.md) §8.)*

---

## Roadmap

Phased, so each step delivers something usable before the next:

1. **UK spike** — ingest and normalize Find a Tender (OCDS) notices; prove the model on one source.
2. **EU spike** — add TED (eForms); prove the unified model handles a second, structurally different source.
3. **Unified dashboard** — search, filter, and triage across both sources in one feed.
4. **Relevance scoring** — explainable rule-based ranking with visible reasons.
5. **Buyer intelligence** — context on the buying organizations (history, patterns). TODO: scope.
6. **AI / RAG** — semantic retrieval and/or LLM-assisted scoring where it beats rules, with explainability preserved as far as possible.
