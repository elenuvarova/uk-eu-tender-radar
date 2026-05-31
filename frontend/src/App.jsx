import { useEffect, useState } from "react";

import { useApi, usePut, useDebouncedValue } from "./lib/api";
import { fmtValue, fmtDate, fmtCount, daysLeft } from "./lib/format";
import {
  NOTICE_TYPES,
  STATUSES,
  COUNTRIES,
  CPV_DIVISIONS,
  scoreBand,
} from "./lib/constants";

const SCORE_CLASS = { strong: "score-high", good: "score-mid", weak: "score-low" };
const BAND_WORD = { strong: "Strong", good: "Good", weak: "Weak" };

// ── small presentationals ─────────────────────────────────────────────────────

function DeadlinePill({ iso }) {
  const d = daysLeft(iso);
  if (d == null) return <span className="pill pill-none">No deadline</span>;
  if (d < 0) return <span className="pill pill-expired">Expired</span>;
  if (d <= 7) return <span className="pill pill-urgent">{d}d left</span>;
  if (d <= 21) return <span className="pill pill-soon">{d}d left</span>;
  return <span className="pill pill-ok">{fmtDate(iso)}</span>;
}

function SourceBadge({ source }) {
  return <span className={`badge badge-${source?.toLowerCase()}`}>{source}</span>;
}

function ScorePill({ relevance }) {
  if (!relevance) return null;
  const s = relevance.score;
  const band = scoreBand(s);
  return (
    <span
      className={`score-pill ${SCORE_CLASS[band]}`}
      title={relevance.reasons.join("\n")}
      aria-label={`Relevance ${s} of 100, ${BAND_WORD[band].toLowerCase()} match`}
    >
      {s}
    </span>
  );
}

// ── buyer panel ───────────────────────────────────────────────────────────────

function BuyerPanel({ buyerId, onClose }) {
  const { data, loading, error } = useApi(`/api/buyers/${buyerId}`, {}, [buyerId]);

  // Esc closes the panel.
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="buyer-panel" role="dialog" aria-label="Buyer profile">
      <div className="buyer-panel-header">
        <span>Buyer profile</span>
        <button className="buyer-close" onClick={onClose} aria-label="Close">✕</button>
      </div>
      {loading && <div className="msg">Loading…</div>}
      {error && <div className="msg msg-error">{error}</div>}
      {data && (
        <>
          <h3 className="buyer-name">{data.canonical_name}</h3>
          {data.country && (
            <div className="buyer-meta">
              {data.country}{data.region ? ` · ${data.region}` : ""}
            </div>
          )}
          {data.name_aliases?.length > 1 && (
            <div className="buyer-aliases">
              Also known as: {data.name_aliases.filter((a) => a !== data.canonical_name).join(", ")}
            </div>
          )}
          <div className="buyer-section-title">Top categories</div>
          {data.top_categories.length === 0 ? (
            <div className="buyer-empty">No category stats yet</div>
          ) : (
            data.top_categories.map((c) => (
              <div key={c.cpv_division} className="buyer-cat-row">
                <span className="pill pill-type">{c.cpv_division}</span>
                <span>{c.notice_count} notice{c.notice_count !== 1 ? "s" : ""}</span>
                {c.avg_value_eur && (
                  <span className="buyer-val">avg {fmtValue(c.avg_value_eur, "EUR")}</span>
                )}
              </div>
            ))
          )}
          <div className="buyer-section-title">Recent notices</div>
          {data.recent_notices.map((n) => (
            <div key={n.id} className="buyer-notice-row">
              <a href={n.source_url} target="_blank" rel="noopener noreferrer">
                {n.title.slice(0, 60)}{n.title.length > 60 ? "…" : ""}
              </a>
              <span className="buyer-notice-date">{fmtDate(n.publication_date)}</span>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

// ── stats row ─────────────────────────────────────────────────────────────────

function StatsRow({ facets, error }) {
  if (error) {
    return (
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Stats unavailable</div>
        </div>
      </div>
    );
  }
  if (!facets) return null;
  return (
    <div className="stats-row">
      <div className="stat-card">
        <div className="stat-value">{fmtCount(facets.total)}</div>
        <div className="stat-label">Total notices</div>
      </div>
      <div className="stat-card">
        <div className="stat-value">{fmtCount(facets.by_source.UK)}</div>
        <div className="stat-label">UK (Find a Tender)</div>
      </div>
      <div className="stat-card">
        <div className="stat-value">{fmtCount(facets.by_source.EU)}</div>
        <div className="stat-label">EU (TED)</div>
      </div>
      <div className="stat-card stat-card-urgent">
        <div className="stat-value">{facets.closing_soon}</div>
        <div className="stat-label">Closing in 7 days</div>
      </div>
    </div>
  );
}

// ── profile panel ─────────────────────────────────────────────────────────────

function ProfilePanel({ profile, onSaved }) {
  const [form, setForm] = useState(null);
  const { put, saving, error } = usePut("/api/profile");

  // Initialise (and re-sync) the form whenever the loaded profile changes —
  // in an effect, not during render.
  useEffect(() => {
    if (!profile) return;
    setForm({
      cpvs: (profile.target_cpv_codes || []).join(", "),
      keywords: (profile.keywords || []).join(", "),
      value_min: profile.value_min ?? "",
      value_max: profile.value_max ?? "",
      countries: (profile.target_countries || []).join(", "),
      min_days: profile.min_days_to_bid ?? 7,
    });
  }, [profile]);

  if (!form) return <div className="profile-loading">Loading profile…</div>;

  const f = (k) => (v) => setForm((p) => ({ ...p, [k]: v }));

  const save = async () => {
    const body = {
      name: profile?.name || "My Company",
      target_cpv_codes: form.cpvs.split(",").map((s) => s.trim()).filter(Boolean),
      keywords: form.keywords.split(",").map((s) => s.trim()).filter(Boolean),
      value_min: form.value_min !== "" ? Number(form.value_min) : null,
      value_max: form.value_max !== "" ? Number(form.value_max) : null,
      value_currency: "EUR",
      target_countries: form.countries.split(",").map((s) => s.trim()).filter(Boolean),
      min_days_to_bid: Number(form.min_days) || 7,
    };
    const saved = await put(body);
    if (saved) onSaved(saved);
  };

  return (
    <div className="profile-panel">
      <div className="profile-header">
        <span>Supplier profile</span>
        <span className="profile-hint">Used to score relevance</span>
      </div>
      <label className="filter-label">
        Target CPV codes <span className="profile-hint">(comma-separated)</span>
      </label>
      <input className="filter-input" value={form.cpvs} onChange={(e) => f("cpvs")(e.target.value)} placeholder="72000000, 48000000" />
      <label className="filter-label">Keywords</label>
      <input className="filter-input" value={form.keywords} onChange={(e) => f("keywords")(e.target.value)} placeholder="cloud, digital, GDPR" />
      <label className="filter-label">Value range (EUR)</label>
      <div className="value-range">
        <input className="filter-input" type="number" value={form.value_min} onChange={(e) => f("value_min")(e.target.value)} placeholder="min" />
        <span>–</span>
        <input className="filter-input" type="number" value={form.value_max} onChange={(e) => f("value_max")(e.target.value)} placeholder="max" />
      </div>
      <label className="filter-label">
        Target countries <span className="profile-hint">(ISO codes)</span>
      </label>
      <input className="filter-input" value={form.countries} onChange={(e) => f("countries")(e.target.value)} placeholder="GB, DE, FR" />
      <label className="filter-label">Min days to bid</label>
      <input className="filter-input" type="number" value={form.min_days} onChange={(e) => f("min_days")(e.target.value)} />
      {error && <div className="msg msg-error" style={{ padding: "8px 0" }}>Save failed: {error}</div>}
      <button className="btn-save" onClick={save} disabled={saving}>
        {saving ? "Saving…" : "Save profile"}
      </button>
    </div>
  );
}

function FilterPanel({ filters, onChange }) {
  const set = (k, v) => onChange({ ...filters, [k]: v });
  const toggle = (k, v) => {
    const arr = filters[k] || [];
    onChange({ ...filters, [k]: arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v] });
  };

  return (
    <aside className="filter-panel">
      <h2 className="filter-heading">Filters</h2>

      <label className="filter-label" htmlFor="kw">Keyword</label>
      <input
        id="kw"
        className="filter-input"
        placeholder="Search title / description…"
        value={filters.q || ""}
        onChange={(e) => set("q", e.target.value)}
      />

      <label className="filter-label" htmlFor="src">Source</label>
      <select id="src" className="filter-select" value={filters.source || ""} onChange={(e) => set("source", e.target.value)}>
        <option value="">All sources</option>
        <option value="UK">UK (Find a Tender)</option>
        <option value="EU">EU (TED)</option>
      </select>

      <fieldset className="check-group">
        <legend className="filter-label">Country</legend>
        {COUNTRIES.map(([code, label]) => (
          <label key={code} className="check-item">
            <input type="checkbox" checked={(filters.country || []).includes(code)} onChange={() => toggle("country", code)} />
            {label}
          </label>
        ))}
      </fieldset>

      <fieldset className="check-group">
        <legend className="filter-label">CPV category</legend>
        {CPV_DIVISIONS.map(([code, label]) => (
          <label key={code} className="check-item">
            <input type="checkbox" checked={(filters.cpv || []).includes(code)} onChange={() => toggle("cpv", code)} />
            {label} ({code})
          </label>
        ))}
      </fieldset>

      <fieldset className="check-group">
        <legend className="filter-label">Notice type</legend>
        {NOTICE_TYPES.map((t) => (
          <label key={t} className="check-item">
            <input type="checkbox" checked={(filters.notice_type || []).includes(t)} onChange={() => toggle("notice_type", t)} />
            {t}
          </label>
        ))}
      </fieldset>

      <fieldset className="check-group">
        <legend className="filter-label">Status</legend>
        {STATUSES.map((s) => (
          <label key={s} className="check-item">
            <input type="checkbox" checked={(filters.status || []).includes(s)} onChange={() => toggle("status", s)} />
            {s}
          </label>
        ))}
      </fieldset>

      <button className="btn-reset" onClick={() => onChange({})}>Reset filters</button>
    </aside>
  );
}

// ── results table ─────────────────────────────────────────────────────────────

function SortBtn({ field, label, sort, onSort }) {
  return (
    <button className={`sort-btn ${sort === field ? "active" : ""}`} onClick={() => onSort(field)}>
      {label}
    </button>
  );
}

function OpportunitiesTable({ state, sort, onSort, onPage, offset, limit, hasProfile, onBuyerClick, onResetFilters }) {
  const { data, loading, error, slow, reload } = state;

  if (error) {
    return (
      <div className="msg msg-error">
        Couldn’t load notices: {error}
        <div>
          <button className="btn-reset" style={{ maxWidth: 160, marginTop: 12 }} onClick={reload}>
            Try again
          </button>
        </div>
      </div>
    );
  }
  if (loading && !data) {
    return (
      <div className="msg">
        {slow
          ? "Waking the server… the free tier spins down when idle, first load can take ~1 min."
          : "Loading…"}
      </div>
    );
  }
  if (!data) return null;

  const { items, total } = data;
  const page = Math.floor(offset / limit);
  const pages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="results-wrap">
      <div className="results-meta">
        {loading ? "Refreshing…" : `${fmtCount(total)} notices`}
        <span className="sort-row">
          Sort:
          <SortBtn field="deadline_asc" label="Deadline ↑" sort={sort} onSort={onSort} />
          <SortBtn field="published_desc" label="Published ↓" sort={sort} onSort={onSort} />
          <SortBtn field="value_desc" label="Value ↓" sort={sort} onSort={onSort} />
        </span>
      </div>

      {items.length === 0 ? (
        <div className="msg msg-empty">
          No notices match these filters.
          <div>
            <button className="btn-reset" style={{ maxWidth: 160, marginTop: 12 }} onClick={onResetFilters}>
              Clear filters
            </button>
          </div>
        </div>
      ) : (
        <table className="opp-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Buyer</th>
              <th>Country</th>
              <th>Value</th>
              <th>Type</th>
              <th>Deadline</th>
              {hasProfile && <th>Score</th>}
              <th aria-label="Open source"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((o) => (
              <tr key={o.id}>
                <td className="cell-title">
                  <SourceBadge source={o.source} />
                  {o.title}
                </td>
                <td className="cell-buyer">
                  {o.buyer_id ? (
                    <button className="buyer-link" onClick={() => onBuyerClick(o.buyer_id)}>
                      {o.buyer_name || "—"}
                    </button>
                  ) : (
                    o.buyer_name || "—"
                  )}
                </td>
                <td>{o.buyer_country || "—"}</td>
                <td className="cell-value">{fmtValue(o.estimated_value, o.currency)}</td>
                <td><span className="pill pill-type">{o.notice_type}</span></td>
                <td><DeadlinePill iso={o.deadline} /></td>
                {hasProfile && <td><ScorePill relevance={o.relevance} /></td>}
                <td>
                  <a className="link-source" href={o.source_url} target="_blank" rel="noopener noreferrer" aria-label="Open original notice">↗</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {pages > 1 && (
        <div className="pagination">
          <button disabled={page === 0} onClick={() => onPage((page - 1) * limit)}>← Prev</button>
          <span>Page {page + 1} of {pages}</span>
          <button disabled={page >= pages - 1} onClick={() => onPage((page + 1) * limit)}>Next →</button>
        </div>
      )}
    </div>
  );
}

// ── app ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [filters, setFilters] = useState({});
  const [sort, setSort] = useState("deadline_asc");
  const [offset, setOffset] = useState(0);
  const [showProfile, setShowProfile] = useState(false);
  const [activeBuyerId, setActiveBuyerId] = useState(null);

  const limit = 25;

  // Profile is the server's copy — no local mirror to drift. Reload after save.
  const profileApi = useApi("/api/profile", {});
  const profile = profileApi.data;
  const hasProfile =
    !!profile &&
    ((profile.target_cpv_codes || []).length > 0 || (profile.keywords || []).length > 0);

  const handleFilters = (f) => { setFilters(f); setOffset(0); };
  const handleSort = (s) => { setSort(s); setOffset(0); };

  // Debounce the keyword so each keystroke doesn't fire an ILIKE scan.
  const debouncedQ = useDebouncedValue(filters.q || "", 350);

  const apiParams = {
    ...filters,
    q: debouncedQ,
    sort,
    limit,
    offset,
    ...(hasProfile ? { score: true } : {}),
  };

  const opps = useApi("/api/opportunities", apiParams);
  const facets = useApi("/api/facets", {});
  const health = useApi("/api/health", {});

  return (
    <div className="app">
      <header className="app-header">
        <h1>UK &amp; EU Procurement Radar</h1>
        <span className="header-sub">
          {health.data && (
            <span className={`db-indicator db-${health.data.db}`} title={`Database: ${health.data.db}`}>
              db: {health.data.db}
            </span>
          )}
          <span className="attr">
            Data:{" "}
            <a href="https://www.find-tender.service.gov.uk" target="_blank" rel="noopener noreferrer">UK FTS (OGL v3)</a>
            {" · "}
            <a href="https://ted.europa.eu" target="_blank" rel="noopener noreferrer">EU TED (© EU)</a>
          </span>
        </span>
      </header>

      <StatsRow facets={facets.data} error={facets.error} />

      <div className="main-layout">
        <div className="left-col">
          <button className="profile-toggle" onClick={() => setShowProfile((p) => !p)}>
            {hasProfile ? "Profile active" : "Set profile"} {showProfile ? "▲" : "▼"}
          </button>
          {showProfile && (
            <ProfilePanel
              profile={profile}
              onSaved={() => { profileApi.reload(); setShowProfile(false); }}
            />
          )}
          <FilterPanel filters={filters} onChange={handleFilters} />
        </div>
        <div className="feed-wrap">
          <OpportunitiesTable
            state={opps}
            sort={sort}
            onSort={handleSort}
            onPage={setOffset}
            offset={offset}
            limit={limit}
            hasProfile={hasProfile}
            onBuyerClick={setActiveBuyerId}
            onResetFilters={() => handleFilters({})}
          />
          {activeBuyerId && (
            <BuyerPanel buyerId={activeBuyerId} onClose={() => setActiveBuyerId(null)} />
          )}
        </div>
      </div>
    </div>
  );
}
