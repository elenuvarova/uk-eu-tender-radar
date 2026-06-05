import { fmtCount } from "../lib/format";

// Lightweight hand-rolled SVG charts — no dependency, themeable via CSS vars,
// each carries a text alternative for screen readers.

const UK = "var(--uk)";
const EU = "var(--eu)";

function polar(cx, cy, r, frac) {
  const a = 2 * Math.PI * frac - Math.PI / 2;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}

function arcPath(cx, cy, r, start, end) {
  const [x1, y1] = polar(cx, cy, r, start);
  const [x2, y2] = polar(cx, cy, r, end);
  const large = end - start > 0.5 ? 1 : 0;
  return `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`;
}

/** Two-slice donut for the UK / EU source split. */
export function SourceDonut({ uk = 0, eu = 0 }) {
  const total = uk + eu;
  const size = 120;
  const cx = size / 2;
  const cy = size / 2;
  const r = 52;
  const hole = 32;
  const ukFrac = total ? uk / total : 0;

  return (
    <div className="chart-card">
      <div className="chart-title">Source split</div>
      <div className="chart-body chart-donut">
        <svg width={size} height={size} role="img" aria-label={`Source split: UK ${uk}, EU ${eu}`}>
          {total === 0 ? (
            <circle cx={cx} cy={cy} r={r} fill="var(--surface2)" />
          ) : (
            <>
              <path d={arcPath(cx, cy, r, 0, ukFrac)} fill={UK} />
              <path d={arcPath(cx, cy, r, ukFrac, 1)} fill={EU} />
              <circle cx={cx} cy={cy} r={hole} fill="var(--surface)" />
            </>
          )}
          <text x={cx} y={cy - 8} textAnchor="middle" dominantBaseline="central" className="donut-total">
            {fmtCount(total)}
          </text>
          <text x={cx} y={cy + 9} textAnchor="middle" dominantBaseline="central" className="donut-sub">
            notices
          </text>
        </svg>
        <ul className="chart-legend">
          <li><span className="dot" style={{ background: UK }} /> UK <b>{fmtCount(uk)}</b></li>
          <li><span className="dot" style={{ background: EU }} /> EU <b>{fmtCount(eu)}</b></li>
        </ul>
      </div>
    </div>
  );
}

/** Horizontal bars for a {label, count}[] series (top N). */
export function BarList({ title, items = [], color = "var(--accent)" }) {
  const max = Math.max(1, ...items.map((d) => d.count));
  const top = items.slice(0, 6);
  const summary = top.map((d) => `${d.label} ${d.count}`).join(", ");
  return (
    <div className="chart-card">
      <div className="chart-title">{title}</div>
      <div className="chart-body">
        {top.length === 0 ? (
          <div className="chart-empty">No data yet</div>
        ) : (
          <div className="bar-list" role="img" aria-label={`${title}: ${summary}`}>
            <ul aria-hidden="true" className="bar-list">
              {top.map((d) => (
                <li key={d.label} className="bar-row">
                  <span className="bar-label" title={d.label}>{d.label}</span>
                  <span className="bar-track">
                    <span className="bar-fill" style={{ width: `${(d.count / max) * 100}%`, background: color }} />
                  </span>
                  <span className="bar-count">{fmtCount(d.count)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

const COMPONENTS = [
  ["sCPV", "CPV"],
  ["sKW", "Keyword"],
  ["sVAL", "Value"],
  ["sDDL", "Deadline"],
  ["sBUY", "Buyer"],
];

/** Five-segment breakdown bars for a relevance score (0–1 per component). */
export function ScoreBreakdown({ breakdown }) {
  if (!breakdown) return null;
  const pct = (v) => {
    const n = Number(v);
    return Number.isFinite(n) ? Math.max(0, Math.min(100, Math.round(n * 100))) : 0;
  };
  const summary = COMPONENTS.map(([key, label]) => `${label} ${pct(breakdown[key])}%`).join(", ");
  return (
    <div className="score-breakdown" role="img" aria-label={`Relevance breakdown: ${summary}`}>
      {COMPONENTS.map(([key, label]) => {
        const w = pct(breakdown[key]);
        return (
          <div key={key} className="sb-row">
            <span className="sb-label">{label}</span>
            <span className="sb-track">
              <span className="sb-fill" style={{ width: `${w}%` }} />
            </span>
          </div>
        );
      })}
    </div>
  );
}
