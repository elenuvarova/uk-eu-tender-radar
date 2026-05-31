import { useEffect, useMemo, useRef, useState } from "react";

import { useApi, usePut, useDebouncedValue } from "./lib/api";
import { useFocusTrap } from "./lib/useFocusTrap";
import { fmtValue, fmtDate, fmtCount, daysLeft } from "./lib/format";
import {
  NOTICE_TYPES,
  STATUSES,
  COUNTRIES,
  CPV_DIVISIONS,
  CPV_DIVISION_LABELS,
  displayCountry,
  scoreBand,
} from "./lib/constants";
import { SourceDonut, BarList, ScoreBreakdown } from "./components/Charts";
import Tour from "./components/Tour";

const SCORE_CLASS = { strong: "score-high", good: "score-mid", weak: "score-low" };
const BAND_WORD  = { strong: "Strong",      good: "Good",     weak: "Weak" };

// ── theme ─────────────────────────────────────────────────────────────────────

function useTheme() {
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark");
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);
  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  return [theme, toggle];
}

// ── helpers ───────────────────────────────────────────────────────────────────

function isDownloadUrl(url) {
  if (!url) return false;
  return /\.(pdf|docx?|xlsx?|zip)(\?.*)?$/i.test(url);
}

function activeFilterCount(filters) {
  return Object.values(filters).filter(
    (v) => v != null && v !== "" && v !== false && (!Array.isArray(v) || v.length > 0)
  ).length;
}

// ── small presentationals ─────────────────────────────────────────────────────

function DeadlinePill({ iso }) {
  const d = daysLeft(iso);
  if (d == null) return <span className="pill pill-none">No deadline</span>;
  if (d < 0)    return <span className="pill pill-expired">Expired</span>;
  // Red pill must stay strictly inside the server "closing in 7 days" window
  // (deadline <= now + 7d). daysLeft() floors, so a 7.x-day deadline returns 7
  // but is NOT in the closing-soon set — hence `< 7`, not `<= 7`. Keep these in
  // sync with the backend deadline window so the pill and the stat card agree.
  if (d < 7)    return <span className="pill pill-urgent">{d}d left</span>;
  if (d <= 21)  return <span className="pill pill-soon">{d}d left</span>;
  return <span className="pill pill-ok">{fmtDate(iso)}</span>;
}

function SourceBadge({ source, onClick, activeSource }) {
  const isActive = activeSource && activeSource === source;
  const clickable = !!onClick;
  return (
    <span
      className={`badge badge-${source?.toLowerCase()} ${clickable ? "badge-clickable" : ""} ${isActive ? "badge-active" : ""}`}
      onClick={onClick}
      title={clickable ? `Filter by ${source}` : source === "UK" ? "UK Find a Tender" : "EU TED"}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={clickable ? (e) => e.key === "Enter" && onClick() : undefined}
      aria-pressed={clickable ? isActive : undefined}
    >
      {source}
    </span>
  );
}

function TypePill({ type, onClick, activeTypes }) {
  const isActive = activeTypes?.includes(type);
  const clickable = !!onClick;
  return (
    <span
      className={`pill pill-type ${clickable ? "badge-clickable" : ""} ${isActive ? "badge-active" : ""}`}
      onClick={onClick}
      title={clickable ? `Filter by ${type}` : undefined}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={clickable ? (e) => e.key === "Enter" && onClick() : undefined}
    >
      {type}
    </span>
  );
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
  const panelRef = useRef(null);
  useFocusTrap(panelRef, true);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="buyer-panel" role="dialog" aria-label="Buyer profile" ref={panelRef}>
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
                <span className="pill pill-type">{CPV_DIVISION_LABELS[c.cpv_division] || c.cpv_division}</span>
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

// ── notice detail drawer ──────────────────────────────────────────────────────

function NoticeDrawer({ noticeId, onClose, onBuyerClick }) {
  const { data, loading, error } = useApi(`/api/opportunities/${noticeId}`, {}, [noticeId]);
  const drawerRef = useRef(null);
  useFocusTrap(drawerRef, true);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const ctaLabel = data?.source === "UK"
    ? "View on Find a Tender ↗"
    : data?.source === "EU"
      ? (isDownloadUrl(data?.source_url) ? "Download document ⬇" : "View on TED ↗")
      : "Open original notice ↗";

  return (
    <div className="drawer-scrim" onClick={onClose}>
      <div
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Notice detail"
        onClick={(e) => e.stopPropagation()}
        ref={drawerRef}
      >
        <div className="drawer-header">
          <span>Notice detail</span>
          <button className="buyer-close" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {loading && <div className="msg">Loading…</div>}
        {error && <div className="msg msg-error">{error}</div>}
        {data && (
          <div className="drawer-body">
            <div className="drawer-badges">
              <SourceBadge source={data.source} />
              <TypePill type={data.notice_type} />
              <span className="pill pill-type">{data.status}</span>
            </div>
            <h2 className="drawer-title">{data.title}</h2>

            <dl className="drawer-facts">
              <div>
                <dt>Buyer</dt>
                <dd>
                  {data.buyer_id ? (
                    <button className="buyer-link" onClick={() => onBuyerClick(data.buyer_id)}>
                      {data.buyer_name || "—"}
                    </button>
                  ) : (
                    data.buyer_name || "—"
                  )}
                </dd>
              </div>
              <div><dt>Country</dt><dd>{displayCountry(data.buyer_country)}</dd></div>
              <div>
                <dt>Value</dt>
                <dd>
                  {data.estimated_value != null
                    ? fmtValue(data.estimated_value, data.currency)
                    : "Value not disclosed"}
                  {data.estimated_value_eur != null && data.currency !== "EUR" && (
                    <span className="drawer-eur"> · {fmtValue(data.estimated_value_eur, "EUR")}</span>
                  )}
                </dd>
              </div>
              <div><dt>Deadline</dt><dd><DeadlinePill iso={data.deadline} /></dd></div>
              <div><dt>Published</dt><dd>{fmtDate(data.publication_date)}</dd></div>
              <div><dt>Procedure</dt><dd>{data.procedure_type || "—"}</dd></div>
            </dl>

            {data.relevance?.breakdown && (
              <>
                <div className="buyer-section-title">
                  Relevance {data.relevance.score} · {BAND_WORD[scoreBand(data.relevance.score)]} match
                </div>
                <ScoreBreakdown breakdown={data.relevance.breakdown} />
                <ul className="drawer-reasons">
                  {data.relevance.reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </>
            )}

            {data.cpv_codes?.length > 0 && (
              <>
                <div className="buyer-section-title">CPV codes</div>
                <div className="drawer-cpvs">
                  {data.cpv_codes.map((c) => (
                    <span key={c} className="pill pill-type" title={CPV_DIVISION_LABELS[c.slice(0, 2)] || c}>{c}</span>
                  ))}
                </div>
              </>
            )}

            {data.description && (
              <>
                <div className="buyer-section-title">Description</div>
                <p className="drawer-desc">{data.description}</p>
              </>
            )}

            {data.award_supplier && (
              <>
                <div className="buyer-section-title">Awarded to</div>
                <p className="drawer-desc">{data.award_supplier}</p>
              </>
            )}

            <a className="btn-save drawer-cta" href={data.source_url} target="_blank" rel="noopener noreferrer">
              {ctaLabel}
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

// ── stats row ─────────────────────────────────────────────────────────────────

function StatCard({ value, label, active, urgent, onClick }) {
  return (
    <button
      type="button"
      className={`stat-card ${urgent ? "stat-card-urgent" : ""} ${active ? "stat-card-active" : ""}`}
      onClick={onClick}
      aria-pressed={active}
      title={`Show ${label}`}
    >
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </button>
  );
}

function StatsRow({ facets, error, filters, onQuick }) {
  if (error) {
    return (
      <div className="stats-row" id="tour-stats">
        <div className="stat-card stat-card-static">
          <div className="stat-label">Stats unavailable right now</div>
        </div>
      </div>
    );
  }
  if (!facets) {
    return (
      <div className="stats-row" id="tour-stats">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="stat-card stat-card-static">
            <div className="stat-value skeleton">0,000</div>
            <div className="stat-label skeleton">Loading</div>
          </div>
        ))}
      </div>
    );
  }
  const showingAll = !filters.source && !filters.closing;
  return (
    <div className="stats-row" id="tour-stats">
      <StatCard value={fmtCount(facets.total)} label="Total notices" active={showingAll} onClick={() => onQuick("all")} />
      <StatCard value={fmtCount(facets.by_source?.UK ?? 0)} label="UK (Find a Tender)" active={filters.source === "UK"} onClick={() => onQuick("UK")} />
      <StatCard value={fmtCount(facets.by_source?.EU ?? 0)} label="EU (TED)" active={filters.source === "EU"} onClick={() => onQuick("EU")} />
      <StatCard value={facets.closing_soon} label="Closing in 7 days" urgent active={!!filters.closing} onClick={() => onQuick("closing")} />
    </div>
  );
}

// ── summary band (charts) ─────────────────────────────────────────────────────

function SummaryBand({ facets }) {
  const [mobileExpanded, setMobileExpanded] = useState(false);
  if (!facets || !facets.total) return null;
  const cpvItems = (facets.by_cpv_division || []).map((d) => ({
    label: CPV_DIVISION_LABELS[d.label] || d.label,
    count: d.count,
  }));
  return (
    <>
      <button
        className="summary-band-toggle"
        onClick={() => setMobileExpanded((e) => !e)}
        aria-expanded={mobileExpanded}
      >
        Overview charts <span>{mobileExpanded ? "▾" : "▸"}</span>
      </button>
      <div className={`summary-band ${mobileExpanded ? "" : "summary-band-collapsed"}`} id="tour-charts">
        <SourceDonut uk={facets.by_source?.UK ?? 0} eu={facets.by_source?.EU ?? 0} />
        <BarList title="Top categories" items={cpvItems} color="var(--accent)" />
        <BarList title="Top countries" items={facets.by_country || []} color="var(--eu)" />
      </div>
    </>
  );
}

// ── profile panel ─────────────────────────────────────────────────────────────

function ProfilePanel({ profile, onSaved }) {
  const [form, setForm] = useState(null);
  const { put, saving, error } = usePut("/api/profile");

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

  // Inline validation — catch mistakes before hitting the API (which would
  // otherwise bounce back an opaque 422).
  const vmin = form.value_min !== "" ? Number(form.value_min) : null;
  const vmax = form.value_max !== "" ? Number(form.value_max) : null;
  const mind = form.min_days !== "" ? Number(form.min_days) : null;
  const cpvTokens = form.cpvs.split(",").map((s) => s.trim()).filter(Boolean);
  const badCpv = cpvTokens.filter((c) => !/^\d{2,8}$/.test(c));

  const errors = {};
  if (form.value_min !== "" && (Number.isNaN(vmin) || vmin < 0)) errors.value_min = "Enter a number ≥ 0";
  if (form.value_max !== "" && (Number.isNaN(vmax) || vmax < 0)) errors.value_max = "Enter a number ≥ 0";
  if (vmin != null && vmax != null && !Number.isNaN(vmin) && !Number.isNaN(vmax) && vmin > vmax)
    errors.value_max = "Max must be ≥ min";
  if (form.min_days !== "" && (Number.isNaN(mind) || mind < 0)) errors.min_days = "Enter a number ≥ 0";
  if (badCpv.length) errors.cpvs = `CPV codes must be 2–8 digits: ${badCpv.join(", ")}`;
  const hasErrors = Object.keys(errors).length > 0;

  const save = async () => {
    if (hasErrors) return;
    const body = {
      name: profile?.name || "My Company",
      target_cpv_codes: [...new Set(cpvTokens)],
      keywords: [...new Set(form.keywords.split(",").map((s) => s.trim()).filter(Boolean))],
      value_min: vmin,
      value_max: vmax,
      value_currency: "EUR",
      target_countries: form.countries.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean),
      min_days_to_bid: mind ?? 7,
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
      <input className={`filter-input ${errors.cpvs ? "input-invalid" : ""}`} value={form.cpvs} onChange={(e) => f("cpvs")(e.target.value)} placeholder="72000000, 48000000" />
      {errors.cpvs && <span className="field-error">{errors.cpvs}</span>}
      <label className="filter-label">Keywords</label>
      <input className="filter-input" value={form.keywords} onChange={(e) => f("keywords")(e.target.value)} placeholder="cloud, digital, GDPR" />
      <label className="filter-label">Value range (EUR)</label>
      <div className="value-range">
        <input className={`filter-input ${errors.value_min ? "input-invalid" : ""}`} type="number" min="0" value={form.value_min} onChange={(e) => f("value_min")(e.target.value)} placeholder="min" />
        <span>–</span>
        <input className={`filter-input ${errors.value_max ? "input-invalid" : ""}`} type="number" min="0" value={form.value_max} onChange={(e) => f("value_max")(e.target.value)} placeholder="max" />
      </div>
      {(errors.value_min || errors.value_max) && (
        <span className="field-error">{errors.value_min || errors.value_max}</span>
      )}
      <label className="filter-label">
        Target countries <span className="profile-hint">(ISO codes)</span>
      </label>
      <input className="filter-input" value={form.countries} onChange={(e) => f("countries")(e.target.value)} placeholder="GB, DE, FR" />
      <label className="filter-label">Min days to bid</label>
      <input className={`filter-input ${errors.min_days ? "input-invalid" : ""}`} type="number" min="0" value={form.min_days} onChange={(e) => f("min_days")(e.target.value)} />
      {errors.min_days && <span className="field-error">{errors.min_days}</span>}
      {error && <div className="msg msg-error" style={{ padding: "8px 0" }}>Couldn't save: {error}</div>}
      <button className="btn-save" onClick={save} disabled={saving || hasErrors} title={hasErrors ? "Fix the highlighted fields first" : undefined}>
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
    <aside className="filter-panel" id="tour-filters">
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

const SORT_FIELDS = [
  { key: "deadline", label: "Deadline" },
  { key: "published", label: "Published" },
  { key: "value", label: "Value" },
];

const SORT_DEFAULTS = { deadline: "asc", published: "desc", value: "desc" };

function SortBtn({ field, label, sort, onSort }) {
  const isActive = sort.field === field;
  const dir = isActive ? sort.dir : SORT_DEFAULTS[field];
  const arrow = dir === "asc" ? "↑" : "↓";
  return (
    <button
      className={`sort-btn ${isActive ? "active" : ""}`}
      onClick={() => onSort(field)}
      aria-label={`Sort by ${label} ${dir === "asc" ? "ascending" : "descending"}`}
    >
      {label} <span className="sort-icon">{isActive ? arrow : "↕"}</span>
    </button>
  );
}

function MobileCardList({ items, hasProfile, onBuyerClick, onNoticeClick, onSourceClick, onTypeClick, filters }) {
  return (
    <div className="mobile-list">
      {items.map((o) => (
        <div key={o.id} className="mobile-card" onClick={() => onNoticeClick(o.id)}>
          <div className="mobile-card-top">
            <div className="mobile-card-tags">
              <SourceBadge
                source={o.source}
                onClick={(e) => { e?.stopPropagation?.(); onSourceClick(o.source); }}
                activeSource={filters.source}
              />
              <TypePill
                type={o.notice_type}
                onClick={(e) => { e?.stopPropagation?.(); onTypeClick(o.notice_type); }}
                activeTypes={filters.notice_type}
              />
            </div>
            <DeadlinePill iso={o.deadline} />
          </div>
          <div className="mobile-card-title">{o.title}</div>
          <div className="mobile-card-meta">
            {o.buyer_id ? (
              <button
                className="buyer-link"
                style={{ fontSize: 12 }}
                onClick={(e) => { e.stopPropagation(); onBuyerClick(o.buyer_id); }}
              >
                {o.buyer_name || "—"}
              </button>
            ) : (
              <span>{o.buyer_name || "—"}</span>
            )}
            <span className="mobile-card-sep">·</span>
            <span>{displayCountry(o.buyer_country)}</span>
            <span className="mobile-card-value">{fmtValue(o.estimated_value, o.currency)}</span>
            {hasProfile && o.relevance && <ScorePill relevance={o.relevance} />}
            <a
              className={isDownloadUrl(o.source_url) ? "link-source link-source-download" : "link-source"}
              href={o.source_url}
              target="_blank"
              rel="noopener noreferrer"
              title={o.source === "UK" ? "View on Find a Tender" : isDownloadUrl(o.source_url) ? "Download document" : "View on TED"}
              onClick={(e) => e.stopPropagation()}
              aria-label="Open source"
              style={{ minWidth: 28, textAlign: "center" }}
            >
              {isDownloadUrl(o.source_url) ? "⬇" : "↗"}
            </a>
          </div>
        </div>
      ))}
    </div>
  );
}

function OpportunitiesTable({ state, sort, onSort, onPage, offset, limit, hasProfile, onBuyerClick, onResetFilters, onNoticeClick, onSourceClick, onTypeClick, filters }) {
  const { data, loading, error, slow, reload } = state;

  if (error) {
    return (
      <div className="msg msg-error">
        Couldn't load notices: {error}
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
  const page  = Math.floor(offset / limit);
  const pages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="results-wrap">
      <div className="results-meta" id="tour-sort">
        {loading ? "Refreshing…" : `${fmtCount(total)} notices`}
        <span className="sort-row">
          Sort:
          {SORT_FIELDS.map(({ key, label }) => (
            <SortBtn key={key} field={key} label={label} sort={sort} onSort={onSort} />
          ))}
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
        <>
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
                <th aria-label="Source link"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((o, idx) => (
                <tr key={o.id} style={{ "--row-i": idx }} id={idx === 0 ? "tour-first-row" : undefined}>
                  <td className="cell-title">
                    <SourceBadge
                      source={o.source}
                      onClick={() => onSourceClick(o.source)}
                      activeSource={filters.source}
                    />
                    <button className="title-link" onClick={() => onNoticeClick(o.id)}>
                      {o.title}
                    </button>
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
                  <td>{displayCountry(o.buyer_country)}</td>
                  <td className="cell-value">{fmtValue(o.estimated_value, o.currency)}</td>
                  <td>
                    <TypePill
                      type={o.notice_type}
                      onClick={() => onTypeClick(o.notice_type)}
                      activeTypes={filters.notice_type}
                    />
                  </td>
                  <td><DeadlinePill iso={o.deadline} /></td>
                  {hasProfile && <td><ScorePill relevance={o.relevance} /></td>}
                  <td>
                    <a
                      className={isDownloadUrl(o.source_url) ? "link-source link-source-download" : "link-source"}
                      href={o.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={o.source === "UK" ? "View on Find a Tender" : isDownloadUrl(o.source_url) ? "Download document" : "View on TED"}
                      aria-label="Open source"
                    >
                      {isDownloadUrl(o.source_url) ? "⬇" : "↗"}
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* mobile card list */}
          <MobileCardList
            items={items}
            hasProfile={hasProfile}
            onBuyerClick={onBuyerClick}
            onNoticeClick={onNoticeClick}
            onSourceClick={onSourceClick}
            onTypeClick={onTypeClick}
            filters={filters}
          />
        </>
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

// ── mobile filter bottom sheet ────────────────────────────────────────────────

function MobileFilterBar({ filters, sort, onOpenSheet }) {
  const count = activeFilterCount(filters);
  const activeField = SORT_FIELDS.find((f) => f.key === sort.field);
  const sortLabel = activeField ? `${activeField.label} ${sort.dir === "asc" ? "↑" : "↓"}` : "";
  return (
    <div className="mobile-filter-bar">
      <button className="mobile-filter-btn" onClick={onOpenSheet}>
        Filters
        {count > 0 && <span className="filter-badge">{count}</span>}
      </button>
      {sortLabel && <span className="mobile-sort-label">Sort: {sortLabel}</span>}
    </div>
  );
}

function MobileFilterSheet({ open, onClose, filters, onChange, profile, onSaved }) {
  const [showProfile, setShowProfile] = useState(false);
  const sheetRef = useRef(null);
  useFocusTrap(sheetRef, open);

  // Escape closes the sheet (other dialogs already do this; the sheet didn't).
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <div className={`filter-sheet-scrim ${open ? "open" : ""}`} onClick={onClose} />
      <div className={`filter-sheet ${open ? "open" : ""}`} role="dialog" aria-label="Filters" ref={sheetRef}>
        <div className="filter-sheet-header">
          <button className="buyer-close" onClick={onClose} aria-label="Close filters">✕</button>
          <span>Filters</span>
          <button className="btn-save" style={{ width: "auto", padding: "4px 16px", margin: 0 }} onClick={onClose}>Done</button>
        </div>
        <div className="filter-sheet-body">
          <FilterPanel filters={filters} onChange={onChange} />
          <div style={{ borderTop: "1px solid var(--border)", padding: "0.5rem 1rem" }}>
            <button className="profile-toggle" onClick={() => setShowProfile((p) => !p)} style={{ width: "100%" }}>
              Supplier profile {showProfile ? "▲" : "▼"}
            </button>
            {showProfile && (
              <ProfilePanel profile={profile} onSaved={(p) => { onSaved(p); setShowProfile(false); }} />
            )}
          </div>
        </div>
      </div>
    </>
  );
}

// ── app ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [filters, setFilters] = useState({});
  const [sort, setSort] = useState({ field: "deadline", dir: "asc" });
  const [offset, setOffset] = useState(0);
  const [showProfile, setShowProfile] = useState(false);
  const [activeBuyerId, setActiveBuyerId] = useState(null);
  const [activeNoticeId, setActiveNoticeId] = useState(null);
  const [showFilterSheet, setShowFilterSheet] = useState(false);
  const [tourActive, setTourActive] = useState(false);
  const [tourPulse, setTourPulse] = useState(false);
  const [theme, toggleTheme] = useTheme();

  const limit = 25;

  const profileApi = useApi("/api/profile", {});
  const profile = profileApi.data;
  const hasProfile =
    !!profile &&
    ((profile.target_cpv_codes || []).length > 0 || (profile.keywords || []).length > 0);

  const handleFilters = (f) => { setFilters(f); setOffset(0); };

  const handleSort = (field) => {
    setSort((prev) => ({
      field,
      dir: prev.field === field
        ? (prev.dir === "asc" ? "desc" : "asc")
        : SORT_DEFAULTS[field],
    }));
    setOffset(0);
  };

  // Quick-filter helpers from table clicks
  const handleSourceClick = (source) => {
    setFilters((f) => ({ ...f, source: f.source === source ? "" : source }));
    setOffset(0);
  };
  const handleTypeClick = (type) => {
    setFilters((f) => {
      const arr = f.notice_type || [];
      return { ...f, notice_type: arr.includes(type) ? arr.filter((x) => x !== type) : [...arr, type] };
    });
    setOffset(0);
  };

  // Quick-filter via the stat cards (source segmented control + closing-soon).
  const handleQuick = (which) => {
    setFilters((f) => {
      if (which === "all") return { ...f, source: "", closing: false };
      if (which === "closing") return { ...f, closing: !f.closing };
      return { ...f, source: f.source === which ? "" : which };
    });
    setOffset(0);
  };

  const debouncedQ = useDebouncedValue(filters.q || "", 350);

  // Convert { field, dir } to the sort param the API expects
  const sortParam = `${sort.field}_${sort.dir}`;

  // "Closing in 7 days" → deadline window. Frozen at mount so the request key
  // is stable (a fresh Date() each render would refetch forever).
  const nowIso = useMemo(() => new Date().toISOString(), []);
  const in7days = useMemo(() => new Date(Date.now() + 7 * 86400000).toISOString(), []);

  // `closing` is a UI-only flag — translate it to the API's deadline params.
  const { closing, ...filterParams } = filters;
  const apiParams = {
    ...filterParams,
    q: debouncedQ,
    sort: sortParam,
    limit,
    offset,
    ...(closing ? { deadline_from: nowIso, deadline_to: in7days } : {}),
    ...(hasProfile ? { score: true } : {}),
  };

  const opps   = useApi("/api/opportunities", apiParams);
  const facets = useApi("/api/facets", {});
  const health = useApi("/api/health", {});

  // Keep pagination in range: if the result set shrank (e.g. filters changed)
  // and the current offset now points past the last page, snap back to page 1.
  // Prevents "Page 6 of 1" and an empty list when data is actually present.
  const oppsTotal = opps.data?.total;
  useEffect(() => {
    if (oppsTotal != null && offset >= oppsTotal && offset > 0) setOffset(0);
  }, [oppsTotal, offset]);

  // Auto-start tour on first visit, after data loads.
  // Dep is `[!!facets.data]` (a boolean) on purpose: it flips false→true exactly
  // once when data arrives, so the effect runs a single time. Depending on the
  // raw `facets.data` object would re-run on every refetch; don't "simplify" it.
  useEffect(() => {
    if (facets.data && !localStorage.getItem("hasSeenTour")) {
      let pulseTimer;
      const t = setTimeout(() => {
        setTourActive(true);
        setTourPulse(true);
        pulseTimer = setTimeout(() => setTourPulse(false), 6500);
      }, 800);
      return () => {
        clearTimeout(t);
        clearTimeout(pulseTimer);
      };
    }
  }, [!!facets.data]);

  const startTour = () => {
    setTourActive(true);
    setTourPulse(false);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>UK &amp; EU Digital Procurement Radar</h1>
        <span className="header-sub">
          {health.data && (
            <span className={`db-indicator db-${health.data.db}`} title={`Database: ${health.data.db}`}>
              db: {health.data.db}
            </span>
          )}
          <button
            className={`tour-btn ${tourPulse ? "tour-pulse" : ""}`}
            onClick={startTour}
            aria-label="Start guided tour"
          >
            Tour
          </button>
          <button className="theme-toggle" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
            {theme === "dark" ? "☀ Light" : "☾ Dark"}
          </button>
          <span className="attr">
            Data:{" "}
            <a href="https://www.find-tender.service.gov.uk" target="_blank" rel="noopener noreferrer">UK FTS (OGL v3)</a>
            {" · "}
            <a href="https://ted.europa.eu" target="_blank" rel="noopener noreferrer">EU TED (© EU)</a>
          </span>
        </span>
      </header>

      <StatsRow facets={facets.data} error={facets.error} filters={filters} onQuick={handleQuick} />
      <SummaryBand facets={facets.data} />

      <div className="main-layout">
        <div className="left-col">
          <button className="profile-toggle" id="tour-profile" onClick={() => setShowProfile((p) => !p)}>
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
            onNoticeClick={setActiveNoticeId}
            onResetFilters={() => handleFilters({})}
            onSourceClick={handleSourceClick}
            onTypeClick={handleTypeClick}
            filters={filters}
          />
          {activeBuyerId && (
            <BuyerPanel buyerId={activeBuyerId} onClose={() => setActiveBuyerId(null)} />
          )}
          {activeNoticeId && (
            <NoticeDrawer
              noticeId={activeNoticeId}
              onClose={() => setActiveNoticeId(null)}
              onBuyerClick={(id) => { setActiveNoticeId(null); setActiveBuyerId(id); }}
            />
          )}
        </div>
      </div>

      {/* mobile bottom filter bar */}
      <MobileFilterBar filters={filters} sort={sort} onOpenSheet={() => setShowFilterSheet(true)} />
      <MobileFilterSheet
        open={showFilterSheet}
        onClose={() => setShowFilterSheet(false)}
        filters={filters}
        onChange={handleFilters}
        profile={profile}
        onSaved={() => { profileApi.reload(); }}
      />

      <Tour active={tourActive} onClose={() => setTourActive(false)} />
    </div>
  );
}
