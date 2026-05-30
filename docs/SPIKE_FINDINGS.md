# Verification Spike — Field Confirmation (RESEARCH §9)

*Run 2026-05-30 against live anonymous APIs. Real samples saved to `spike/fixtures/` (`fts_release_package.json`, `ted_search.json`). Purpose: confirm the field paths flagged ⚠️ unverified before writing the normalization mappers. No code rewritten.*

## Outcome: all ⚠️ paths resolved ✅

| Item flagged ⚠️ | Result | Evidence (from live sample) |
|---|---|---|
| FTS wire OCDS version | ✅ `1.1` | `version: "1.1"` |
| FTS cursor pagination | ✅ present | `links.next` non-empty on a 7-day page |
| UK `cpv_codes` path (tender vs items) | ✅ **use `tender.classification`** | tender notice had `tender.classification = {scheme:CPV, id:"45000000"}` while `tender.items[0].classification = None`. **Read `tender.classification` first; items often empty.** |
| UK `source_notice_id` / source_url | ✅ `release.id` (form `NNNNNN-YYYY`) | `release.id = "051000-2026"`, `ocid = "ocds-h6vhtk-06a94b"`. Buyer ref `buyer.id = "GB-FTS-182486"`. URL: `https://www.find-tender.service.gov.uk/Notice/{release.id}` |
| UK buyer region | ✅ `parties[buyer].address.region` (ITL) | `region = "UKI"`, `countryName = "United Kingdom"`. Resolve via `parties[]`, not `buyer`. |
| UK procedure mapping | ✅ | `procurementMethod = "selective"`, `procurementMethodDetails = "Restricted procedure"`, `status = "active"` |
| EU `notice-title` shape | ✅ flat `lang→str`, key `eng` | English present at `["eng"]`; 24-language map. |
| EU `buyer-name` shape | ✅ `lang→[str]` (array) | `{"fra": ["Région Hauts-de-France"]}` — different shape from title; handle both. |
| EU CPV duplicates | ✅ dedup needed | `["72262000","72262000","72262000","72262000"]` |
| EU `place-of-performance` (NUTS) | ✅ NUTS+country, with dups | `["FRE11","FRA","FRE11","FRA"]` → take NUTS (`FRE11`), dedup. |
| **EU deadline (was the big unknown)** | ✅ **present on `competition`, absent on `result`** | `cn-standard/competition` → `deadline-receipt-tender-date-lot = ["2026-06-12+02:00"]`; `can-standard/result` → `None`. Confirms deadline is real on open tenders. |
| EU value | ✅ both `total-value` and `estimated-value-lot` | competition notice: `total-value=600000 ["EUR"]`, `estimated-value-lot=["600000"]`. Some `result` notices have `None` (expected). |
| EU `source_url` template | ✅ confirmed | from `links`: HTML `https://ted.europa.eu/en/notice/{pubnum}/html`, XML `.../en/notice/{pubnum}/xml`. Per-language paths (`/de/`, `/fr/`…). |
| EU publication-date format | ✅ `YYYY-MM-DD+HH:MM` | `"2026-05-29+02:00"` (carries offset) |

## Mapper decisions locked in (feed back into normalize/)

1. **UK CPV:** read `tender.classification.id` (scheme=CPV) as primary; fall back to `tender.items[].classification` / `.additionalClassifications`. Don't assume items is populated.
2. **UK identity:** `source_notice_id = release.id`; `source_url = https://www.find-tender.service.gov.uk/Notice/{release.id}`. Keep `ocid` in `raw_json`. Buyer location from `parties[role=buyer].address`.
3. **EU title:** `notice-title["eng"]`; fall back to official language if `eng` missing.
4. **EU buyer name:** `buyer-name[lang][0]` (array) — pick `eng`/official lang, take first element.
5. **EU dedup:** de-duplicate every flattened array (`classification-cpv`, `place-of-performance`, etc.) on ingest.
6. **EU NUTS:** parse `place-of-performance` → keep NUTS codes (alpha+digits), drop bare country codes already in `buyer-country`.
7. **EU deadline:** `deadline-receipt-tender-date-lot[0]` (nullable; expect null on `result`/`can` and PIN notices).
8. **EU source_url:** `https://ted.europa.eu/en/notice/{publication-number}/html`.
9. **Notice/form-type → enum:** EU `form-type` drives `notice_type` (`competition`→TENDER, `result`→AWARD, `planning`→PLANNING); UK `tag[]` drives it. Both keep raw.

## Residual notes
- **FTS rate limit** still undocumented numerically — throttle + back off on 429 (unchanged guidance).
- **eForms→OCDS conversion:** the spike read the TED **Search API** field model directly (not the OCDS-for-eForms profile). Either path works; the Search API field names above are sufficient for the mapper and avoid a conversion step. Decision: **ingest EU via the Search API field model directly**, store raw in `raw_json`.
- TED `total-value` on `result` notices can be null even when an award exists — rely on lot-level / award fields for awarded value later.

## Fixtures
- `spike/fixtures/fts_release_package.json` — 20 UK tender-stage releases (188 KB)
- `spike/fixtures/ted_search.json` — 10 EU active digital notices (113 KB)

These double as the first **mapper unit-test fixtures** (DEV_PLAN §7).
