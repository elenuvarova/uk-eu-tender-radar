# UK & EU Procurement Radar — Documentation

A cross-border public-procurement intelligence tool for small digital/edtech suppliers. It ingests open UK (Find a Tender / OCDS) and EU (TED / eForms) notices, normalizes them into one unified model, scores relevance, and surfaces matching opportunities.

## Documents

| Doc | Purpose | Status |
|---|---|---|
| [RESEARCH.md](./RESEARCH.md) | Verified findings: APIs, field mapping, CPV niche, scoring formula, feasibility, competitors, legal | ✅ Complete (some field paths flagged ⚠️ for build-time confirmation) |
| [DEV_PLAN.md](./DEV_PLAN.md) | FastAPI architecture, 7-phase build plan, ops, testing, risks | ✅ Complete |
| [DATA_MODEL.md](./DATA_MODEL.md) | Full SQLModel schema: tables, columns, indexes, relationships, lifecycle | ✅ Complete |
| [API_CONTRACT.md](./API_CONTRACT.md) | REST contract between React frontend and FastAPI backend | ✅ Draft (lets frontend + backend build in parallel) |
| [SPIKE_FINDINGS.md](./SPIKE_FINDINGS.md) | Field-confirmation spike: live FTS+TED samples resolving the ⚠️ paths before mappers | ✅ Complete (2026-05-30) |
| [GLOSSARY.md](./GLOSSARY.md) | Domain terms (OCDS, eForms, CPV, NUTS, BT codes, etc.) | ✅ Complete |
| [portfolio/CASE_STUDY.md](./portfolio/CASE_STUDY.md) | Portfolio write-up (honest TODOs; metrics filled in as the build progresses) | 🟡 Skeleton |

## Single sources of truth (avoid duplication drift)

- **Data model** → DATA_MODEL.md (SQLModel tables). Other docs reference, not restate.
- **Source field mapping** → RESEARCH.md §4.
- **Scoring formula** → RESEARCH.md §5.
- **API surface** → API_CONTRACT.md.

## Key decisions taken

- **Stack:** Full Python — React + Vite frontend, FastAPI backend, SQLModel over SQLite (local) / Supabase Postgres (prod).
- **Name:** "UK & EU Procurement Radar" (kept for the portfolio build; revisit before any public launch — collides with the existing TenderRadar product).
- **Niche:** digital / edtech / software-services tenders only (CPV-filtered).
- **Scoring:** explainable rule-based first; RAG/LLM deferred to post-MVP.
- **Sources:** Find a Tender (UK) + TED v3 (EU), both anonymous. Contracts Finder skipped for MVP.

## Current repo state

The repo still contains the original **Node/Express/Sequelize** template. Per the FastAPI decision, the backend is rebuilt in Python in **Phase 0** (DEV_PLAN.md §8); the React frontend and the Render/Docker scaffolding are reused.

## Recommended next step

The pre-build verification spike is **done** ([SPIKE_FINDINGS.md](./SPIKE_FINDINGS.md)) — all ⚠️ field paths confirmed against live FTS + TED data, with sample fixtures saved. Next: **Phase 0** — migrate the backend to FastAPI (DEV_PLAN.md §8) and stand up the `TenderOpportunity` model, then write the mappers in Phases 1–2 using the saved fixtures as unit-test inputs.
