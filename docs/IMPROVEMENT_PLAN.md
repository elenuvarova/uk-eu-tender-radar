# Improvement Plan — Correctness Hardening + UX/UI Uplift

_Status: PLAN ONLY. Nothing here is executed yet. Produced from a 3-track audit (backend correctness, frontend correctness, UX/UI design) on 2026-05-31._

---

## 0. Why we keep hitting "one more error"

The bugs aren't random. They share four root causes. Fix the roots and the symptom-stream stops.

1. **SQLite locally, Postgres in production — and every test runs on SQLite.**
   So Postgres-only failures ship undetected. Already burned us twice (Infinity-in-JSON, prepared statements) and there are at least **two more** of the exact same kind sitting unfired (TED Infinity, `DISTINCT` over a JSON column).

2. **We patch the symptom, not the cause.**
   Timezone handling is hand-patched in **four** separate places instead of fixing the column type once. The Infinity fix went into the UK mapper but not the EU mapper. Each patch leaves the twin bug alive elsewhere.

3. **No fault isolation in ingestion.**
   One bad record aborts the *entire* batch (single `commit()` at the end), and a broad `except Exception` in the mappers silently *deletes* any notice with an unexpected shape. So "1 weird notice" becomes "0 notices ingested" or "notices vanish with no trace."

4. **Missing defensive guards.**
   Division-by-zero in scoring, unvalidated profile input, no request timeout/cancellation on the frontend.

The single highest-leverage preventive fix is **#1: add a Postgres-backed test tier** (Phase E). It's the net that would have caught everything we hand-fixed.

---

## Phase A — Critical correctness (blocks production / current ingestion)

> These are confirmed, not speculative. A1 will break your **next** ingestion run.

### A1. EU/TED mapper has the same Infinity/NaN JSON bug we just fixed in UK 🔴 BLOCKS TED INGEST
- **File:** `backend/app/ingestion/normalize/eforms.py:281` — returns `"raw_json": notice` raw, with **zero** sanitization (`grep -c _json_safe eforms.py` → 0; OCDS has 4).
- **Effect:** identical to commit `10c451e`. The TED step of the GitHub Action will crash on the first notice containing an `Infinity`/`NaN` JSON token, rolling back the whole TED batch.
- **Fix:** lift `_json_safe` into a shared `app/ingestion/normalize/_util.py` and call it in eForms exactly as OCDS does: `"raw_json": _json_safe(notice)`.

### A2. CPV filter will 500 on Postgres (`SELECT DISTINCT` over a `json` column) 🔴
- **File:** `backend/app/api/opportunities.py:56-61` — `select(TenderOpportunity)…join(TenderCpv)…distinct()`. The selected entity includes the `raw_json` JSON column; PostgreSQL `json` has no equality operator, so `DISTINCT` raises `could not identify an equality operator for type json`. SQLite tolerates it → tests pass, prod breaks.
- **Effect:** every `?cpv=` request (a primary filter) 500s once data is on Postgres.
- **Fix:** replace the join+distinct with an `EXISTS`/`IN` subquery:
  `stmt.where(TenderOpportunity.id.in_(select(TenderCpv.tender_id).where(or_(*[TenderCpv.cpv_code.startswith(p) for p in cpv]))))`. Removes row-multiplication and the need for `distinct()`. (Optional: migrate `raw_json` → `JSONB` for indexing later.)

### A3. `score_value` raises ZeroDivisionError on real inputs 🔴
- **File:** `backend/app/scoring/relevance.py:85-90` — divides by `lo` or `v` with no zero guard. A profile with `value_min = 0`, or any notice with `estimated_value_eur = 0`, throws. Since scoring runs per-row inside the listing with no try/except, **one** such row 500s the whole scored feed.
- **Fix:** guard each division (`… if lo else 0.0`, `… if v else 0.0`) or normalize `v<=0`/`lo<=0`/`hi<=0` to the neutral case up front. Pair with A6 (profile validation).

### A4. Ingestion is all-or-nothing 🟠
- **File:** `backend/app/ingestion/run.py:24-48` — builds every row then a single `session.commit()`. Any one failure rolls back the entire run. Mappers isolate per-record *normalize* errors but persistence has no isolation.
- **Fix:** per-record `try` + `session.begin_nested()` (savepoint) + outer commit; count `failed` alongside `inserted`/`updated` and log skipped `tender_id`s.

### A5. TED award-supplier crash silently drops whole notices 🟠
- **File:** `backend/app/ingestion/normalize/eforms.py:250` → `_pick_lang` (`:64-83`) calls `.keys()` and throws `AttributeError` when `winner-name` is a `list`/`str` (a shape TED emits). The fallback at `:251-255` is unreachable. The broad `except` then discards the entire award notice → corrupts `awarded_count` in buyer rollup.
- **Fix:** make `_pick_lang` handle `str`/`list`/`dict` at the top; remove the dead fallback. Separately, narrow the mapper `except` or at least count+surface dropped records so silent loss is visible.

### A6. Profile input is unvalidated 🟠
- **File:** `backend/app/api/profile.py:27-36` — blindly `setattr`s every client field. No `value_min ≥ 0`, no `value_max ≥ value_min`, no `min_days ≥ 0`. A bad save directly triggers A3.
- **Fix:** dedicated `ProfileUpdate` Pydantic schema with validators (don't bind the table model to the request body).

---

## Phase B — Postgres/SQLite robustness (kill the root causes)

### B1. Store timezone-aware datetimes properly (removes the recurring tz bug class) 🟠
- **Files:** `backend/app/models/tender.py` (all datetime cols are `DateTime()` = naive) + a new Alembic migration.
- Mappers produce **aware** UTC datetimes; naive columns make Postgres drop the offset and return naive on read — the reason tz is hand-patched in `relevance.py:99-100`, `relevance.py:172-173`, `api/opportunities.py:28-29`.
- **Fix:** use `DateTime(timezone=True)` for `publication_date, deadline, fx_rate_date, created_at, updated_at`; migration `ALTER COLUMN … TYPE timestamptz`; then **delete** the four scattered `if tzinfo is None` patches.

### B2. Deterministic pagination 🟡
- **File:** `api/opportunities.py:127-138` — sorts on a single non-unique column; Postgres can skip/repeat rows across pages. Add `.order_by(…, TenderOpportunity.id.asc())` tiebreaker to all branches.

### B3. One owner for the schema (Alembic), backfill missing migrations 🟠
- `db.py` runs `create_all` on every startup **and** there's an Alembic baseline — but the baseline only covers `tender_opportunity` + `tender_cpv`. `buyer`, `buyer_category_stat`, `supplier_profile`, `saved_search` have **no migration** and exist only via `create_all`.
- **Fix:** generate the missing migrations; drop `init_db()`/`create_all` from the production lifespan; rely on `alembic upgrade head` (already in the Docker CMD).

### B4. Connection hygiene for the Supabase pooler 🟡
- `prepare_threshold=0` is in place (good). Consider `poolclass=NullPool` (or small pool + `pool_pre_ping`) for the transaction pooler to avoid holding server-side state across pooled connections.

### B5. `_val_reason` dead branch + `score_deadline` truncation 🟡
- `relevance.py:159-164`: `s == 0.5` branch is unreachable (caught by `s >= 0.5` above) → "Value not disclosed" never shows; undisclosed value mislabeled. Reorder.
- `relevance.py:101-102`: `.days` truncates → a tender closing later *today* scores like one already closed. Use `total_seconds()/86400`.

### B6. NUTS / CPV normalization edge cases 🟡
- `eforms.py:99-109` drops valid 3-char NUTS-1 codes (`UKI`) via `len>3`; OCDS uses a different regex. Standardize on `^[A-Z]{2}\d` (digit after country prefix) in both mappers. Normalize CPV check-digit suffix (`72500000-0` vs `72500000`) at ingest.

---

## Phase C — Frontend correctness

### C1. Out-of-order responses corrupt the table (race condition) 🔴
- **File:** `frontend/src/App.jsx:29-40` (`useApi`) — no request cancellation. Rapid filter/keystroke/paging changes resolve in arbitrary order; the grid can show results that don't match the visible filters.
- **Fix:** `AbortController` per request, ignore stale resolutions, abort on cleanup. Also fixes the unmount warning when the buyer panel closes mid-flight.

### C2. No timeout → 50s Render cold start looks like a frozen app 🟠
- **File:** `App.jsx:31-37` — `fetch` with no timeout, bare "Loading…".
- **Fix:** `AbortSignal.timeout(~60s)` + a "waking the server (~50s)…" message after ~3s. (Ties into D1.)

### C3. Keyword search refetches on every keystroke 🟠
- **File:** `App.jsx:248-254` → `apiParams` → refetch per character (each an unindexed `ILIKE '%…%'`). Debounce ~300ms (a `useDebouncedValue` hook).

### C4. Score color thresholds miscalibrated 🟠
- **File:** `App.jsx:126` — `s>=65` high / `>=40` mid / else low. But sub-scores default to **0.5 neutral**, so an *irrelevant* notice floats ~50-60 and shows **amber**, not red. Recalibrate (e.g. `≥70 / ≥55 / else`) or have the backend emit a calibrated band. Pin with a test.

### C5. `setState` during render 🟡
- **Files:** `App.jsx:408` and `ProfilePanel:181-190`. Works by luck of a guard, fragile under StrictMode. Sync in `useEffect` or derive from the fetch result; drop the duplicated `profile` mirror (single source of truth).

### C6. `CLOSED` status filter returns nothing 🟡
- `STATUSES` (`App.jsx:163`) includes `CLOSED`, but CLOSED is **synthetic** (computed at response time, never stored), so `WHERE status IN ('CLOSED')` matches zero rows even though CLOSED pills are visible. Either remove it from the FE list or add backend support for filtering effective status.

### C7. Misc 🟢
- `frontend/index.html` `<title>` still says "Full-Stack Template".
- `reload` returned by `useApi` is unused — wire it to retry buttons (D1) and post-save refresh (C5).
- Unused `defaultdict` import in `api/opportunities.py:1`.

---

## Phase D — UX/UI uplift (make it look like a product)

> Build order suggestion: **D1 → D2 → D3 → D4 → D5 → D6 → D7/D8.** States first (every visit hits them), then the scoring spine, then polish.

### D1. First-class states (S–M)
Replace the developer-facing placeholders:
- **Skeletons** shaped like the real widgets/rows instead of "Loading…".
- **Cold-start:** after >3s show "Waking the radar… free-tier server, first load can take ~1 min." Clear on `health` response.
- **Empty DB:** drop the `python -m app.ingestion…` CLI text; show "No notices yet" + Retry.
- **Zero results:** "No matches with these filters" + Clear-filters + an `include_unspecified_value` toggle (value is missing on 30-50% of notices — a silent culprit).
- **Errors:** friendly message + visible **Try again** (wire `reload`), never a raw `HTTP 500`.

### D2. Profile onboarding as a first-run flow (M)
Scoring is the product, but it's hidden behind a collapsed `👤 Set profile` toggle most users never open.
- When no profile: a centered setup card over a faded feed — the activation moment.
- **Chip pickers, not comma text:** CPV as labeled category chips ("Software (48)", "IT services (72)", "E-learning (80)", "Research (79)", "R&D (73)"), keyword tokens with suggestions, country chips, value-range presets ("£50k-£500k" …).
- On save: dismiss, sort by relevance, animate scored rows in, toast: "Scored 128 live notices — 9 strong matches."
- After set: collapse to a compact summary chip-bar ("IT services · Software · 3 keywords · GB, DE · ✎ Edit").

### D3. Make the relevance score the hero (M) — _needs a backend change_
Today it's a 12px pill with a hover-only `title` tooltip (keyboard/touch can't read it).
- **Per-row score rail:** left-edge colored bar + number + a 5-segment micro-breakdown (CPV/keyword/value/deadline/buyer) as inline SVG. Add a tier word ("Strong/Good/Weak") so it's not color-alone.
- **Breakdown in the detail drawer:** labeled horizontal bars (component · weight · fill · reason text with ✅/⚠️). Optional 5-axis radar (we have exactly 5 components — apt and striking on dark).
- **Backend dependency:** the feed currently returns only `{score, reasons[]}` (strings). Expose per-component sub-scores (the data model already has `RelevanceScoreCache.breakdown_json` with `sCPV/sKW/sVAL/sDDL/sBUY`) and structured `reasons[]`.
- **Architectural note (important):** scoring is computed **after** pagination, per page, and there is **no `relevance_desc` sort**. So "show my best matches first" doesn't actually work across the dataset — only the 25 deadline-sorted rows get annotated. To make relevance the hero it must be **precomputed into a cache table per profile** and the listing must `ORDER BY` it. This is the biggest single architectural item in the plan. (See D3b.)

### D3b. Wire up the score cache (M–L)
- Compute scores in a job (on ingest and on profile-save) into `RelevanceScoreCache(profile_id, opportunity_id, score, breakdown_json, valid_until)`.
- Listing joins the cache when `score=true` → enables true `sort=relevance_desc` and removes per-request scoring cost.

### D4. Notice detail drawer (M)
There's no in-app detail view — the only "more" is the external `↗`, forcing users off-site to triage. `GET /api/opportunities/{id}` already exists and is unused.
- Right-side overlay drawer: full title + lang, key facts (buyer, country, value original+EUR, deadline countdown, procedure), score breakdown (D3), all CPV chips (matched highlighted), full description, award info, **one** primary CTA "Open original notice ↗", secondary Save/Copy.
- Convert the existing **buyer panel** into the same drawer component (one drawer, two contents). Fixes its a11y too: focus-trap on open, **Esc** to close, focus-restore on close, `role="dialog"`, scrim.

### D5. "Radar summary" band with charts (M) — the portfolio "wow"
Four inert number cards waste the best screen space; the richest endpoints aren't visualized.
- **Source split** donut (`facets.by_source`, UK green / EU blue).
- **Top categories** horizontal bar (`facets.by_cpv_division`).
- **UK-vs-EU by category** diverging bar (`/api/dashboard/uk-vs-eu`) — the signature cross-border visual.
- **Closing-soon** sparkbar (today / ≤7 / ≤14 / ≤30d) and, when scored, a **score distribution** histogram.
- **Library:** Recharts for the donut/bars/diverging (already named in the case study); hand-rolled inline SVG for the per-row rail/sparkbars (zero dependency). Each chart needs a text alternative for a11y.

### D6. Results redesign for scannability (M)
- Offer a **card/list view** (default for triage) with a **table toggle** for power comparison.
- Score-driven visual priority: left-border intensity by score, urgency dot for ≤7d, bolder value for top-quartile, **tabular figures** so columns don't jitter.
- Whole row clickable → detail drawer; `↗` becomes a secondary action.
- **Sortable headers done right:** real `<button>` in `<th>` with `aria-sort` + ▲/▼. Add a relevance sort (after D3b).
- Consider cursor pagination / "Load more" (the API model is cursor-based; the code uses offset).

### D7. Visual polish (S–M)
- Formalize an **elevation scale** (surface/elevated/overlay + subtle shadows + 1px top highlight) and a **spacing ramp** (4/8px tokens) — paddings are currently ad-hoc.
- Replace **emoji** (`🎯👤▲▼`) with a single stroke-icon set (Lucide: radar, sliders, user, chevrons, external-link, x).
- Add `:focus-visible` rings and a `prefers-reduced-motion` block (both absent today).
- Reserve `--accent` for the single primary action per surface; let UK/EU hues carry source identity; `--urgent`/`--warn` strictly for deadlines/scores.
- Subtle micro-interactions (row hover lift, chip select, drawer slide, number count-up), 1-2 elements per view.

### D8. Responsive / mobile (M)
- Single-column stack < 768px; summary becomes a scroll-snap carousel; filters move to a bottom-sheet/drawer; card view becomes the only results view.
- Full-screen drawers on mobile; touch targets ≥44px; use `dvh` not `vh`.

### D-a11y (binding, WCAG 2.2 AA — fold into the above)
- Score breakdown must be keyboard/touch reachable (move into drawer/focusable popover; `aria-label` on the chip).
- Drawers: focus management + Esc.
- `<fieldset>/<legend>` around filter checkbox groups; `aria-label` on icon-only buttons; `aria-sort` on sortable headers.
- Verify contrast on muted-text-on-surface and score pills; never rely on color alone (add tier words / labels).
- Charts need `aria-label`/visually-hidden summaries.

---

## Phase E — Testing & CI (so this doesn't recur)

### E1. Postgres-backed integration tier 🟠 (highest preventive value)
Run the existing API tests against a Postgres container, not just SQLite. Would have caught A1, A2, B1, B2 before deploy.

### E2. Edge-input fixtures
- Infinity/NaN in raw JSON (both sources), `estimated_value_eur = 0` and `value_min = 0` (A3), `winner-name` as `str` and `list` (A5), NUTS-1 codes (B6), re-run-ingest idempotency (no duplicate CPV rows / stable counts).

### E3. Frontend tests
- A runner isn't configured. Add Vitest + React Testing Library; pin score→color bands (C4), pagination edge math, and "rapid param changes don't apply stale data" (C1).

---

## Suggested sequencing

| Step | Scope | Why now |
|---|---|---|
| **1. Phase A (A1-A6)** | Critical correctness | A1 blocks your current TED ingest; A2/A3 break core features on Postgres. Small, surgical. |
| **2. Phase E1-E2** | Postgres tests | Lock the fixes so they can't regress; catch the rest. |
| **3. Phase B** | Root-cause robustness | Ends the tz/schema/pagination bug-stream. |
| **4. Phase C** | Frontend correctness | Race + cold-start are demo-visible. |
| **5. Phase D1-D4** | States, onboarding, score hero, drawer | The product/portfolio leap. (D3b backend cache is the meatiest.) |
| **6. Phase D5-D8** | Charts, results redesign, polish, responsive | The visual "wow." |

Phases A-C are mostly small, surgical diffs. Phase D is the larger build and where the portfolio value is.
