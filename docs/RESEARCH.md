# UK & EU Procurement Radar — Research Synthesis

*Compiled 2026-05-30. Findings below were produced by parallel research streams; API endpoints, auth, pagination, and licences were verified by **live anonymous HTTP calls** to both APIs on 2026-05-30 unless flagged otherwise. Items that could not be confirmed are marked **⚠️ unverified** and must be re-checked during the build.*

---

## 1. Executive summary

A cross-border UK+EU procurement intelligence tool for small digital/edtech suppliers is **feasible on open data with no API keys** for the MVP, and sits in a **genuinely underserved niche**: the strongest UK tools (Tussell, Stotles) are UK-only by design, and the pan-European players under-emphasise UK depth. Both source APIs allow anonymous read access to published notices, both datasets are openly licensed for commercial reuse with attribution.

The hard part is **normalization**: UK Find a Tender publishes OCDS 1.1 JSON; EU TED publishes eForms (lot-centric, multilingual). Both must collapse into one `TenderOpportunity` model without losing meaning.

**Key strategic findings:**
- ✅ UK source confirmed: **Find a Tender Service (FTS)** — anonymous OCDS 1.1 API with proper cursor pagination.
- ✅ EU source confirmed: **TED API v3** — anonymous search API, expert query language, English available per-notice.
- ⚠️ Naming risk: an active competitor **TenderRadar** (tenderradar.io/.eu) does almost exactly this for EU SMEs. *Decision taken: keep "UK & EU Procurement Radar" as it's a portfolio piece; revisit before any public launch.*
- ⚠️ Two data-quality landmines: **missing `estimated_value`** (30–50% of notices) and **buyer entity resolution** (free-text buyer names don't reconcile across sources).

---

## 2. UK source — Find a Tender Service (FTS)

**Recommendation: use FTS as the single UK source for the MVP.** Contracts Finder is optional/secondary (legacy + below-threshold backfill only).

### Endpoint (verified live, HTTP 200, anonymous)
- Base: `https://www.find-tender.service.gov.uk`
- Primary harvest: `GET /api/1.0/ocdsReleasePackages`
- Per-notice: `https://www.find-tender.service.gov.uk/Notice/{noticeId}/OCDS/ReleasePackage`

```
GET https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?updatedFrom=2026-05-20T00:00:00Z&updatedTo=2026-05-21T00:00:00Z&limit=100
```
Params: `updatedFrom`, `updatedTo`, `stages`, `limit`, `cursor`. **`updatedFrom` must be full ISO-8601 datetime** — date-only returns HTTP 400.

### Key facts (verified)
| Aspect | Finding |
|---|---|
| Auth | **Anonymous — no key, no registration.** |
| Format | OCDS wire `version: "1.1"` (FTS docs map to OCDS 1.1.5 + extensions, incl. EU profile + UK extension) |
| Pagination | **Cursor-based** via `links.next` — follow until absent. Page size 100. |
| Freshness | Near-real-time (notices minutes old on same-day query) |
| History | Enhanced FTS from 24 Feb 2025 (Procurement Act 2023); legacy notices back to 2 Mar 2021 |
| Licence | **Open Government Licence v3.0** — commercial reuse OK with attribution |
| Coverage | Above + below threshold (except below-threshold Scotland) |
| `ocid` form | `ocds-h6vhtk-xxxxxx` |
| Rate limit | Undocumented numeric; 429 under bursts. **Throttle conservatively, back off on 429.** ⚠️ |

### Contracts Finder (secondary, optional)
- `GET /Published/Notices/OCDS/Search` — anonymous, but **flat package, NO pagination cursor** (`links: null`), and **aggressive rate limit: ~12 req / 2 min** (verified 429 "Rate limit of 12 exceeded. Please retry after 120 seconds"). OCDS 1.0+partial-1.1 (lower fidelity). Different ocid prefix (`ocds-b5fd17-`) — dedupe across sources on content, not ocid. **Skip for MVP.**

---

## 3. EU source — TED API v3

**Recommendation: use the anonymous TED Search API.** No key, no signup.

### Endpoint (verified live, HTTP 200, anonymous, no auth header)
- Search: `POST https://api.ted.europa.eu/v3/notices/search`
- Retrieve: per-notice links returned in response (`https://ted.europa.eu/en/notice/{publication-number}/xml|html|pdf`)
- Swagger: `https://api.ted.europa.eu/swagger`

```bash
curl -X POST "https://api.ted.europa.eu/v3/notices/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "buyer-country IN (BEL NLD DEU FRA) AND publication-date>=20260501 SORT BY publication-date DESC",
    "fields": ["publication-number","notice-title","buyer-name","buyer-country",
               "classification-cpv","total-value","total-value-cur","notice-type",
               "form-type","procedure-type","place-of-performance"],
    "page": 1, "limit": 50, "paginationMode": "ITERATION", "scope": "ACTIVE"
  }'
```
`fields` is **mandatory**. Returns `{ notices[], totalNoticeCount, iterationNextToken, timedOut }`.

### Key facts (verified)
| Aspect | Finding |
|---|---|
| Auth | **Anonymous for published notices** (confirmed by docs + live calls). Key only needed to publish unpublished notices. |
| Query | Expert query language: `=`, `IN (A B C)`, `>=`, `AND/OR/NOT`, `SORT BY`, full-text `FT="..."`. Dates `YYYYMMDD`. Country = ISO **alpha-3**. |
| Pagination | `PAGE_NUMBER`: max 250/page, **15,000 total cap**. `ITERATION` (scroll via `iterationNextToken`): **no cap — use this for harvesting.** |
| Scope | `ALL` (last 10y), `LATEST`, `ACTIVE` (open competitions) |
| Rate limit | Fair-use per IP: ~700 req/min, 600 downloads/6min, 3 concurrent bulk |
| Bulk | Daily/monthly packages, no login: `https://ted.europa.eu/packages/daily/{YYYYNNNNN}` |
| Coverage | All 27 EU + EEA + institutions. BE/NL/DE/FR confirmed live (1,174 notices since 1 May 2026). >700k notices/yr. |
| Format | **eForms** (mandatory since ~Oct 2023; legacy submission closed 31 Jan 2024). Search API normalises both to eForms business-term model. |
| Licence | Notices: freely reusable under **Commission Decision 2011/833/EU** (attribution good practice). Metadata CC0; editorial CC BY 4.0. |

### eForms shape gotchas (verified)
- `notice-title` is a flat `lang→string` map (`{"eng": "..."}`); but `buyer-name` / `description-lot` are `lang→[string]` **arrays**. Handle both.
- Fields return **duplicated values** (lots/proc flattened) — **dedupe on ingest.**
- eForms is **lot-centric**: title/value/deadline/CPV often at `tender.lots[]`, not procedure level. Coalesce procedure-then-lot.
- English: read `eng` key; fall back to official language (`BT-702`) when missing.
- ⚠️ `deadline-receipt-tender-date-lot` was ABSENT on the award notices sampled — confirm against a live **competition** notice before relying on it.

---

## 4. Unified data model & normalization

**Approach: use OCDS as the common intermediate representation.** Ingest UK as native OCDS 1.1; convert EU eForms via the [OCDS-for-eForms profile](https://standard.open-contracting.org/profiles/eforms/latest/en/) rules. This eliminates most per-source branching.

### Field mapping (condensed)
| Unified field | UK OCDS 1.1 | EU eForms (BT code → OCDS) |
|---|---|---|
| `title` | `tender.title` | BT-21 → `tender.title` / `tender.lots[].title` |
| `buyer_name` | `buyer.name` (via `parties[]`) | BT-500 → `parties[role=buyer].name` |
| `buyer_country` | `parties[buyer].address.countryName` | BT-514 → `parties[].address.countryName` |
| `buyer_region` | `parties[buyer].address.region` (ITL) | BT-507 NUTS3 → `parties[].address.region` |
| `description` | `tender.description` | BT-24 → `tender.description`/lot |
| `cpv_codes` | `tender.classification.id` **AND** `tender.items[].classification.id` (read both!) | BT-262/263 → `tender.items[].classification` |
| `estimated_value` | `tender.value.amount` | BT-27 → `tender.value.amount` / lot |
| `currency` | `tender.value.currency` | BT-27 currency attr |
| `publication_date` | `releases[].date` | BT-05 → `date` ⚠️ |
| `deadline` | `tender.tenderPeriod.endDate` | BT-131 → `tender.tenderPeriod.endDate` ⚠️ |
| `notice_type` | `tag[]` | form-type/subtype → `tag[]` |
| `procedure_type` | `tender.procurementMethod` (+Details) | BT-105 → `procurementMethod` |
| `status` | `tender.status` | derived from notice subtype |
| `award_supplier` | `awards[].suppliers[].name` | BT-500 of winner → `awards[].suppliers[]` |
| `source_url` | construct from notice id | construct from publication-number ⚠️ |

⚠️ Unverified paths to confirm against one real converted sample before build: BT-701/`source_notice_id`, OJEU publication-date OCDS field, TED `source_url` template, whether eForms profile sets `tender.classification` vs only item-level.

### Resolve organisations via `parties[]`
OCDS stores buyer location in `parties[]` (referenced from `buyer.id`), **not** under `buyer` directly. `buyer` is only `{id, name}`. Same for suppliers via `roles: [supplier]`.

### Common enums (both sources map in; keep raw value alongside)
- **notice_type:** `PLANNING | TENDER | AWARD | CONTRACT | MODIFICATION | OTHER`
- **procedure_type:** `OPEN | SELECTIVE | LIMITED | DIRECT | OTHER` (OCDS only has 4 methods; eForms BT-105 has many → map down, keep `procedure_type_raw`)
- **status:** `PLANNED | OPEN | CLOSED | AWARDED | UNSUCCESSFUL | CANCELLED` (`CLOSED` is synthetic = `active` + `deadline < now`)

### Normalization landmines
1. **Currency** — store original `value`+`currency` verbatim; add derived `estimated_value_eur` from a dated FX snapshot (store rate + date). Never overwrite source.
2. **Multilingual** — store chosen string + `title_lang`; keep all variants in `raw_json`.
3. **NUTS vs ITL** — store `buyer_region_raw` + normalized `buyer_region_code` + `buyer_country`. Don't assume cross-source region codes join; normalize country first.
4. **Missing fields** — everything except identity fields is nullable. Coalesce procedure→lot.
5. **Dedup** — primary key `source + ocid`; collapse multiple releases per ocid into current state + timeline. Cross-source secondary guard: fuzzy `(title, buyer_name, deadline, value)`.
6. **Dates** — store TZ-aware UTC, but retain original offset for `deadline` (open/closed must be evaluated in buyer's local time). Date-only deadline = end-of-day local.

### CPV include-list for digital/edtech niche
- **Tier 1 (always):** division `48` (software packages), `72` (IT services — optionally exclude `72100000` hardware).
- **Tier 2 (with narrowing):** `79310000, 79311300, 79315000, 79320000, 79330000, 79340000` (market/social research, analytics, UX proxy); `80420000` (e-learning), `80530000`/`80533xxx` (computer training), `80300000` (higher ed).
- **Tier 3 (only if co-occurring with Tier 1):** `73100000, 73200000, 73300000` (R&D), `79400000` (mgmt consultancy).
- Implementation: store CPV array + denormalized child table; qualify a notice if **any** CPV hits the list (prefix match).

---

## 5. Relevance scoring (rule-based, explainable)

Score = weighted sum of 5 normalized sub-scores × 100. Country is a **hard pre-filter**, not scored.

```
score = round(100 * (0.35·sCPV + 0.25·sKW + 0.15·sVAL + 0.15·sDDL + 0.10·sBUY))
```

| # | Component | Weight | Computation |
|---|---|---:|---|
| C1 | CPV match | 35 | `max` over tender×profile CPV pairs of longest-shared-prefix score: exact=1.0, class(4)=0.7, group(3)=0.45, division(2)=0.25 |
| C2 | Keyword | 25 | title hit=1.0, desc hit=0.6; saturates at ~half the profile keywords matched |
| C3 | Value in range | 15 | in-band=1.0; below/above decay linearly/hyperbolically; **null=0.5 neutral** |
| C4 | Days-to-deadline | 15 | expired=0; too-soon steep penalty; window [min,45d]=1.0; far-out mild decay floor 0.6; **null=0.5** |
| C5 | Buyer repeat | 10 | from `BuyerCategoryStat`: 0 past=0, 1–2=0.5, 3–5=0.8, ≥6=1.0 |

Every sub-score maps to a tier → auto-generates an audit bullet ("✅ Value: £850k sits inside your £200k–£2m band"). **CPV granularity is the dominant lever.** Weights live in a `SCORE_WEIGHTS` config for later A/B tuning; results cached per (profile, tender) with `valid_until = next local midnight`.

---

## 6. Feature feasibility

| Feature | Verdict | Limitation |
|---|---|---|
| Unified feed + filters | ✅ Feasible | Value filter drops 30–50% of notices (offer "include unspecified value" toggle) |
| Tender card | ✅ Feasible | Graceful "Value not disclosed" placeholders |
| Relevance score | ✅ Feasible | C5 weak until history accrues; core (CPV+keyword = 60%) solid immediately |
| Buyer profile | ⚠️ Partial | **Buyer entity resolution is the core risk** — free-text names don't reconcile; award history sparse |
| Dashboard (by country, closing soon, top buyers/categories) | ✅ Feasible | Roll CPV to division for readable buckets |
| Market heatmap | ✅ Feasible | Default count-weighted (value-weighted degraded by missing values) |
| UK vs EU comparison | ⚠️ Partial | Value comparisons apples-to-oranges (GBP/EUR, different thresholds) — frame as directional |
| Saved searches | ✅ Feasible | No source dependency |

**Extra tables beyond `TenderOpportunity`:** `SupplierProfile`, `SavedSearch`, `Buyer` (entity resolution + `buyer_id` FK on opportunities), `BuyerCategoryStat` (pre-aggregated rollup), `RelevanceScoreCache`, `FxRate`. Plus a `TenderCpv(tender_id, cpv_code, cpv_division)` child table for index-friendly prefix filtering, and FTS on title/description (Postgres `tsvector`).

---

## 7. Competitive landscape

| Product | Coverage | Free tier | Position |
|---|---|---|---|
| **Tussell** | **UK only** | No | Enterprise intelligence |
| **Stotles** | **UK only** | ✅ Freemium | SME, AI-forward — closest modern analogue |
| **Mercell** | 30+ EU countries incl. UK | Trial | Heavy enterprise multi-country incumbent |
| **OpenOpps** / Spend Network | Global incl. TED | ✅ Free search | Breadth over polish, weak niche filtering |
| **TenderRadar** ⚠️ | 27 EU + TED | Unverified | **Closest direct competitor** — AI + translation + scoring for EU SMEs |
| TenderNed (NL) | NL only | Free | National utility |

**The gap:** no mainstream tool gives a genuine **unified UK+EU view for SMEs**. Cross-border participation is structurally tiny (<5% non-domestic bids; only ~7% of authorities get a foreign bid) — blocked by *information access + language*, not capability. Providing English docs roughly **doubles** foreign participation on low-value contracts. The wedge: cross-border + niche (digital/edtech) + relevance-over-volume + SME-friendly price. Open data is the *input*; the value-add is curation, normalization, translation, scoring, and UX.

---

## 8. Legal / compliance

✅ **Both datasets are reusable for this project, including commercially, with attribution.**
- **UK FTS:** Open Government Licence v3.0 → *"Contains public sector information licensed under the Open Government Licence v3.0."*
- **EU TED:** notices reusable under Commission Decision 2011/833/EU → *"Source: TED — © European Union, [year]."*

**Compliance checklist:** attribution footer for both; no crests/EU logos; treat named contacts in notices as **personal data (UK GDPR/GDPR)** — minimise, don't re-broker; respect API rate limits (cache, don't hammer); keep an attributions page (OGL↔CC BY 4.0 compatible).

---

## 9. Pre-build verification checklist

Before/at the start of the build, confirm these flagged items against live data. **Field-confirmation done 2026-05-30 — see [SPIKE_FINDINGS.md](./SPIKE_FINDINGS.md).**
- [ ] One full paginated FTS harvest (follow `links.next`) to ground-truth daily volume + 429 thresholds *(deferred to Phase 1 — `links.next` presence confirmed)*
- [x] One live FTS **tender-stage** release package + one live EU notice confirmed: `cpv_codes` paths (UK uses `tender.classification`), `source_notice_id` (UK `release.id`, EU `publication-number`), publication-date field, TED `source_url` template (`https://ted.europa.eu/en/notice/{n}/html`), deadline field present on an active competition notice ✅
- [ ] EU `FT="..."` full-text operator + default scope/limit *(not exercised yet)*
- [ ] Current TED rate-limit thresholds (developers' corner) *(still undocumented numerically)*
- [ ] FX source for GBP↔EUR (dated snapshots) *(pick in Phase 2)*

---

## Source agents (for follow-up)
The five research agents remain resumable for deeper digs:
- UK APIs: `a443f2e662a355019` · EU TED: `aca28d948fe2bd171` · Mapping: `a67455986d7d110db` · Market: `aa9baa6715b5a42a9` · Scoring/feasibility: `a0348a4ba91df180a`
