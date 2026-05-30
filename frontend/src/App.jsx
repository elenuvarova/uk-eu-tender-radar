import { useEffect, useState, useCallback } from "react";

// ── data hooks + mutation ─────────────────────────────────────────────────────

function usePut(path) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const put = async (body) => {
    setSaving(true); setError(null);
    try {
      const r = await fetch(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) { setError(e.message); return null; }
    finally { setSaving(false); }
  };
  return { put, saving, error };
}

function buildUrl(path, params) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (Array.isArray(v)) v.forEach((x) => x && url.searchParams.append(k, x));
    else if (v !== "" && v !== null && v !== undefined) url.searchParams.set(k, v);
  });
  return url.toString();
}

function useApi(path, params = {}, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const fetch_ = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }));
    fetch(buildUrl(path, params))
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((e) => setState({ data: null, loading: false, error: e.message }));
  }, [JSON.stringify(params)]);
  useEffect(() => { fetch_(); }, [fetch_, ...deps]);
  return { ...state, reload: fetch_ };
}

// ── formatting helpers ────────────────────────────────────────────────────────

function fmtValue(value, currency) {
  if (value == null) return "—";
  const sym = currency === "GBP" ? "£" : currency === "EUR" ? "€" : (currency || "");
  const n = value >= 1_000_000
    ? `${(value / 1_000_000).toFixed(1)}M`
    : value >= 1_000
    ? `${Math.round(value / 1_000)}k`
    : String(value);
  return `${sym}${n}`;
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function daysLeft(iso) {
  if (!iso) return null;
  const diff = Math.round((new Date(iso) - Date.now()) / 86400000);
  return diff;
}

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
  const cls = s >= 65 ? "score-high" : s >= 40 ? "score-mid" : "score-low";
  return (
    <span className={`score-pill ${cls}`} title={relevance.reasons.join("\n")}>
      {s}%
    </span>
  );
}

// ── stats row ─────────────────────────────────────────────────────────────────

function StatsRow({ facets }) {
  if (!facets) return null;
  return (
    <div className="stats-row">
      <div className="stat-card">
        <div className="stat-value">{facets.total.toLocaleString()}</div>
        <div className="stat-label">Total notices</div>
      </div>
      <div className="stat-card">
        <div className="stat-value">{(facets.by_source.UK || 0).toLocaleString()}</div>
        <div className="stat-label">UK (Find a Tender)</div>
      </div>
      <div className="stat-card">
        <div className="stat-value">{(facets.by_source.EU || 0).toLocaleString()}</div>
        <div className="stat-label">EU (TED)</div>
      </div>
      <div className="stat-card stat-card-urgent">
        <div className="stat-value">{facets.closing_soon}</div>
        <div className="stat-label">Closing in 7 days</div>
      </div>
    </div>
  );
}

// ── filters ───────────────────────────────────────────────────────────────────

const NOTICE_TYPES = ["PLANNING", "TENDER", "AWARD", "CONTRACT", "MODIFICATION"];
const STATUSES = ["PLANNED", "OPEN", "CLOSED", "AWARDED", "UNSUCCESSFUL", "CANCELLED"];
const COUNTRIES = [
  ["GB", "United Kingdom"], ["DE", "Germany"], ["FR", "France"],
  ["BE", "Belgium"], ["NL", "Netherlands"], ["IE", "Ireland"],
  ["ES", "Spain"], ["IT", "Italy"], ["PL", "Poland"],
];
const CPV_DIVISIONS = [
  ["48", "Software"], ["72", "IT services"], ["80", "Education"],
  ["79", "Business services"], ["73", "R&D"],
];

// ── profile panel ─────────────────────────────────────────────────────────────

function ProfilePanel({ profile, onSave }) {
  const [form, setForm] = useState(null);
  const { put, saving } = usePut("/api/profile");

  // Initialise form from profile (once loaded)
  if (!form && profile) {
    setForm({
      cpvs: (profile.target_cpv_codes || []).join(", "),
      keywords: (profile.keywords || []).join(", "),
      value_min: profile.value_min ?? "",
      value_max: profile.value_max ?? "",
      countries: (profile.target_countries || []).join(", "),
      min_days: profile.min_days_to_bid ?? 7,
    });
  }

  if (!form) return <div className="profile-loading">Loading profile…</div>;

  const save = async () => {
    const parsed = {
      id: "default",
      name: profile?.name || "My Company",
      target_cpv_codes: form.cpvs.split(",").map(s => s.trim()).filter(Boolean),
      keywords: form.keywords.split(",").map(s => s.trim()).filter(Boolean),
      value_min: form.value_min !== "" ? Number(form.value_min) : null,
      value_max: form.value_max !== "" ? Number(form.value_max) : null,
      value_currency: "EUR",
      target_countries: form.countries.split(",").map(s => s.trim()).filter(Boolean),
      min_days_to_bid: Number(form.min_days) || 7,
    };
    const saved = await put(parsed);
    if (saved) onSave(saved);
  };

  const f = (k) => (v) => setForm(p => ({ ...p, [k]: v }));

  return (
    <div className="profile-panel">
      <div className="profile-header">
        <span>🎯 Supplier Profile</span>
        <span className="profile-hint">Used to score relevance</span>
      </div>
      <label className="filter-label">Target CPV codes <span className="profile-hint">(comma-separated)</span></label>
      <input className="filter-input" value={form.cpvs} onChange={e => f("cpvs")(e.target.value)} placeholder="72000000, 48000000" />
      <label className="filter-label">Keywords</label>
      <input className="filter-input" value={form.keywords} onChange={e => f("keywords")(e.target.value)} placeholder="cloud, digital, GDPR" />
      <label className="filter-label">Value range (EUR)</label>
      <div className="value-range">
        <input className="filter-input" type="number" value={form.value_min} onChange={e => f("value_min")(e.target.value)} placeholder="min" />
        <span>–</span>
        <input className="filter-input" type="number" value={form.value_max} onChange={e => f("value_max")(e.target.value)} placeholder="max" />
      </div>
      <label className="filter-label">Target countries <span className="profile-hint">(ISO codes)</span></label>
      <input className="filter-input" value={form.countries} onChange={e => f("countries")(e.target.value)} placeholder="GB, DE, FR" />
      <label className="filter-label">Min days to bid</label>
      <input className="filter-input" type="number" value={form.min_days} onChange={e => f("min_days")(e.target.value)} />
      <button className="btn-save" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save profile"}</button>
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

      <label className="filter-label">Keyword</label>
      <input
        className="filter-input"
        placeholder="Search title / description…"
        value={filters.q || ""}
        onChange={(e) => set("q", e.target.value)}
      />

      <label className="filter-label">Source</label>
      <select className="filter-select" value={filters.source || ""} onChange={(e) => set("source", e.target.value)}>
        <option value="">All sources</option>
        <option value="UK">UK (Find a Tender)</option>
        <option value="EU">EU (TED)</option>
      </select>

      <label className="filter-label">Country</label>
      <div className="check-group">
        {COUNTRIES.map(([code, label]) => (
          <label key={code} className="check-item">
            <input type="checkbox" checked={(filters.country || []).includes(code)}
              onChange={() => toggle("country", code)} />
            {label}
          </label>
        ))}
      </div>

      <label className="filter-label">CPV category</label>
      <div className="check-group">
        {CPV_DIVISIONS.map(([code, label]) => (
          <label key={code} className="check-item">
            <input type="checkbox" checked={(filters.cpv || []).includes(code)}
              onChange={() => toggle("cpv", code)} />
            {label} ({code})
          </label>
        ))}
      </div>

      <label className="filter-label">Notice type</label>
      <div className="check-group">
        {NOTICE_TYPES.map((t) => (
          <label key={t} className="check-item">
            <input type="checkbox" checked={(filters.notice_type || []).includes(t)}
              onChange={() => toggle("notice_type", t)} />
            {t}
          </label>
        ))}
      </div>

      <label className="filter-label">Status</label>
      <div className="check-group">
        {STATUSES.map((s) => (
          <label key={s} className="check-item">
            <input type="checkbox" checked={(filters.status || []).includes(s)}
              onChange={() => toggle("status", s)} />
            {s}
          </label>
        ))}
      </div>

      <button className="btn-reset" onClick={() => onChange({})}>Reset filters</button>
    </aside>
  );
}

// ── results table ─────────────────────────────────────────────────────────────

function OpportunitiesTable({ data, loading, error, sort, onSort, onPage, offset, limit, hasProfile }) {
  if (error) return <div className="msg msg-error">Failed to load: {error}</div>;
  if (loading && !data) return <div className="msg">Loading…</div>;
  if (!data) return null;

  const { items, total } = data;
  const page = Math.floor(offset / limit);
  const pages = Math.ceil(total / limit);

  const SortBtn = ({ field, label }) => (
    <button className={`sort-btn ${sort === field ? "active" : ""}`} onClick={() => onSort(field)}>
      {label}
    </button>
  );

  return (
    <div className="results-wrap">
      <div className="results-meta">
        {loading ? "Refreshing…" : `${total.toLocaleString()} notices`}
        <span className="sort-row">
          Sort: <SortBtn field="deadline_asc" label="Deadline ↑" />
          <SortBtn field="published_desc" label="Published ↓" />
          <SortBtn field="value_desc" label="Value ↓" />
        </span>
      </div>

      {items.length === 0
        ? <div className="msg msg-empty">No notices match these filters. Try ingesting data first:<br />
            <code>python -m app.ingestion.run --source fts --days 7</code>
          </div>
        : <table className="opp-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Buyer</th>
                <th>Country</th>
                <th>Value</th>
                <th>Type</th>
                <th>Deadline</th>
                {hasProfile && <th>Score</th>}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((o) => (
                <tr key={o.id}>
                  <td className="cell-title">
                    <SourceBadge source={o.source} />
                    {o.title}
                  </td>
                  <td className="cell-buyer">{o.buyer_name || "—"}</td>
                  <td>{o.buyer_country || "—"}</td>
                  <td className="cell-value">{fmtValue(o.estimated_value, o.currency)}</td>
                  <td><span className="pill pill-type">{o.notice_type}</span></td>
                  <td><DeadlinePill iso={o.deadline} /></td>
                  {hasProfile && <td><ScorePill relevance={o.relevance} /></td>}
                  <td>
                    <a className="link-source" href={o.source_url} target="_blank" rel="noopener noreferrer">↗</a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
      }

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
  const [profile, setProfile] = useState(null);
  const [showProfile, setShowProfile] = useState(false);

  const limit = 25;

  // Load profile on mount
  const profileApi = useApi("/api/profile", {});
  if (profileApi.data && !profile) setProfile(profileApi.data);

  const hasProfile = profile && (
    (profile.target_cpv_codes || []).length > 0 ||
    (profile.keywords || []).length > 0
  );

  const handleFilters = (f) => { setFilters(f); setOffset(0); };
  const handleSort = (s) => { setSort(s); setOffset(0); };

  const apiParams = { ...filters, sort, limit, offset, ...(hasProfile ? { score: true } : {}) };

  const opps = useApi("/api/opportunities", apiParams);
  const facets = useApi("/api/facets", {});
  const health = useApi("/api/health", {});

  return (
    <div className="app">
      <header className="app-header">
        <h1>UK &amp; EU Procurement Radar</h1>
        <span className="header-sub">
          {health.data ? (
            <span className={`db-indicator db-${health.data.db}`}>
              db: {health.data.db}
            </span>
          ) : ""}
          <span className="attr">
            Data: <a href="https://www.find-tender.service.gov.uk" target="_blank" rel="noopener noreferrer">UK FTS (OGL v3)</a>
            {" · "}
            <a href="https://ted.europa.eu" target="_blank" rel="noopener noreferrer">EU TED (© EU)</a>
          </span>
        </span>
      </header>

      <StatsRow facets={facets.data} />

      <div className="main-layout">
        <div className="left-col">
          <div className="profile-toggle" onClick={() => setShowProfile(p => !p)}>
            {hasProfile ? "🎯 Profile active" : "👤 Set profile"} {showProfile ? "▲" : "▼"}
          </div>
          {showProfile && <ProfilePanel profile={profile} onSave={p => { setProfile(p); setShowProfile(false); }} />}
          <FilterPanel filters={filters} onChange={handleFilters} />
        </div>
        <OpportunitiesTable
          data={opps.data}
          loading={opps.loading}
          error={opps.error}
          sort={sort}
          onSort={handleSort}
          onPage={setOffset}
          offset={offset}
          limit={limit}
          hasProfile={hasProfile}
        />
      </div>
    </div>
  );
}
