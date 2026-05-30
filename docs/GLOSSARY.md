# Glossary — UK & EU Procurement Radar

Domain terms used across the docs. Skim this first if procurement/open-data jargon is unfamiliar.

## Data standards & formats

- **OCDS (Open Contracting Data Standard)** — the JSON standard the UK's Find a Tender publishes in. Organized around a contracting *lifecycle* (planning → tender → award → contract → implementation) as a series of **releases**. v1.1 here. [standard.open-contracting.org](https://standard.open-contracting.org/1.1/en/)
- **eForms** — the EU's standard electronic forms for procurement notices, mandatory on TED since ~Oct 2023. Field values are identified by **BT codes**; structure is **lot-centric**. [docs.ted.europa.eu/eforms](https://docs.ted.europa.eu/eforms/latest/)
- **OCDS-for-eForms profile** — official mapping rules converting eForms → OCDS. We use it so EU data lands in the same shape as UK data. [profile](https://standard.open-contracting.org/profiles/eforms/latest/en/)
- **release / release package** — OCDS unit of publication. A `releasePackage` wraps one or more `releases[]`; a single notice may emit several releases over its lifecycle.
- **BT code** (Business Term) — eForms field identifier, e.g. `BT-21` (title), `BT-24` (description), `BT-27` (value), `BT-105` (procedure type), `BT-131` (submission deadline), `BT-500` (org name), `BT-507` (NUTS subdivision), `BT-514` (country).

## Identifiers & classifications

- **CPV (Common Procurement Vocabulary)** — 8-digit EU code classifying *what* is being bought. Hierarchical: `DDGGSSSS` — 2-digit **division**, 3-digit **group**, 4-digit **class**, then finer. Our niche filter targets divisions `48` (software) and `72` (IT services) plus selected `79`/`80`/`73` codes. [reference](https://ted.europa.eu/simap/codes-and-nomenclatures/cpv)
- **NUTS** — EU regional geocoding (NUTS1/2/3). EU buyer regions come as NUTS3 codes (e.g. `BE100`).
- **ITL (International Territorial Levels)** — the UK's post-Brexit successor to NUTS; codes are largely NUTS-compatible. UK buyer regions may be ITL codes or free text — hence we store both raw and normalized region.
- **ocid (Open Contracting ID)** — stable per-process identifier in OCDS. UK FTS uses prefix `ocds-h6vhtk-`; Contracts Finder uses `ocds-b5fd17-` (so the two don't share ocids — dedupe on content, not ocid).
- **publication-number** — TED's stable notice ID (e.g. `367714-2026`). Our primary key for EU records.

## Sources & systems

- **FTS (Find a Tender Service)** — the UK central procurement notice platform (post-Procurement-Act-2023). Our UK source. OCDS API, anonymous.
- **Contracts Finder (CF)** — older UK platform for below-threshold + legacy notices. *Skipped for MVP* (aggressive rate limit, no pagination, lower OCDS fidelity).
- **TED (Tenders Electronic Daily)** — the EU's official journal supplement for procurement. Our EU source. v3 search API, anonymous.
- **Procurement Act 2023** — UK legislation; enhanced FTS launched under it on 24 Feb 2025.

## Notice lifecycle & types (our common enums)

- **notice_type** — `PLANNING` (early heads-up / PIN), `TENDER` (open competition / contract notice), `AWARD` (result / contract award notice), `CONTRACT`, `MODIFICATION`, `OTHER`.
- **procedure_type** — `OPEN` (anyone can bid), `SELECTIVE` (shortlist/restricted, competitive dialogue, etc.), `LIMITED` (negotiated without a call), `DIRECT` (direct award), `OTHER`.
- **status** — `PLANNED`, `OPEN`, `CLOSED` (synthetic: open competition whose deadline has passed but no result yet), `AWARDED`, `UNSUCCESSFUL`, `CANCELLED`.
- **PIN (Prior Information Notice)** — an early signal a buyer *may* tender something; no deadline. Maps to `PLANNING`.
- **CAN (Contract Award Notice)** — announces who won; carries supplier but usually no deadline. Maps to `AWARD`.
- **above/below threshold** — whether a contract's value exceeds the regulated value triggering full publication obligations. Affects which platform/coverage applies.

## Product & scoring terms

- **TenderOpportunity** — our unified internal record; every notice from any source normalizes into it. (Schema: DATA_MODEL.md.)
- **SupplierProfile** — the "lens" a user defines (target CPVs, keywords, value band, countries) that opportunities are scored against.
- **relevance score** — explainable 0–100 rule-based fit score (RESEARCH.md §5); never ML in the MVP.
- **buyer entity resolution** — reconciling inconsistent free-text buyer names into one canonical `Buyer` so per-buyer stats are trustworthy. A known hard problem and a core data risk.
- **RAG (Retrieval-Augmented Generation)** — LLM technique (retrieve relevant text, feed to a model) reserved for post-MVP features (summaries, bid/no-bid, ask-the-notice).

## Licences

- **OGL v3.0 (Open Government Licence)** — the UK FTS data licence; permits commercial reuse with attribution.
- **Commission Decision 2011/833/EU** — the basis for reusing TED notices freely (attribution good practice). TED metadata is CC0; editorial content CC BY 4.0.
