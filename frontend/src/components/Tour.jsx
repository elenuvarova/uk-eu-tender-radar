import { useEffect, useLayoutEffect, useState } from "react";

const STEPS = [
  {
    targetId: "tour-stats",
    title: "At a glance",
    body: "Live counts across all notices. Tap a card to filter instantly — the red one shows tenders closing this week.",
    position: "below",
  },
  {
    targetId: "tour-charts",
    title: "Market overview",
    body: "Source split and top categories show where procurement demand is concentrated right now.",
    position: "below",
  },
  {
    targetId: "tour-filters",
    title: "Narrow the list",
    body: "Filter by keyword, source (UK or EU), country, CPV category, and notice type. Changes apply instantly — no submit needed.",
    position: "right",
  },
  {
    targetId: "tour-sort",
    title: "Sorting",
    body: "Sort by closest deadline, most recently published, or highest value. Click an active sort again to reverse direction.",
    position: "below",
  },
  {
    targetId: "tour-first-row",
    title: "Open a notice",
    body: "Click any title to read full details in a side panel. UK notices link to Find a Tender; EU notices may open a PDF on TED.",
    position: "below",
  },
  {
    targetId: "tour-profile",
    title: "Relevance scoring",
    body: "Set your CPV codes and keywords here. Once saved, every notice gets a relevance score (0–100) so the best matches surface first.",
    position: "right",
  },
];

const TOOLTIP_WIDTH = 300;
const TOOLTIP_HEIGHT = 200;
const TOOLTIP_GAP = 12;

const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

/**
 * Track the on-screen rect of the current step's target.
 * Recomputes when the step changes AND whenever the tour activates (the target
 * may not have existed at mount), plus on scroll/resize so the spotlight tracks
 * the element. Returns null if the target can't be found.
 */
function useTargetRect(targetId, active) {
  const [rect, setRect] = useState(null);

  useLayoutEffect(() => {
    if (!active || !targetId) {
      setRect(null);
      return;
    }

    let raf = 0;
    const measure = () => {
      const el = document.getElementById(targetId);
      if (!el) {
        setRect(null);
        return;
      }
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    };

    // Bring the target into view, then measure on the next frame.
    const el = document.getElementById(targetId);
    if (el) el.scrollIntoView({ block: "center", behavior: "smooth" });
    raf = requestAnimationFrame(measure);

    window.addEventListener("scroll", measure, true);
    window.addEventListener("resize", measure);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", measure, true);
      window.removeEventListener("resize", measure);
    };
  }, [targetId, active]);

  return rect;
}

function Tooltip({ cfg, stepIndex, total, rect, onNext, onSkip }) {
  if (!rect) return null;

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const pad = 16;

  let top, left;
  if (cfg.position === "below") {
    top = rect.top + rect.height + TOOLTIP_GAP;
    left = rect.left + rect.width / 2 - TOOLTIP_WIDTH / 2;
  } else if (cfg.position === "right") {
    top = rect.top;
    left = rect.left + rect.width + TOOLTIP_GAP;
  } else {
    top = rect.top - TOOLTIP_HEIGHT - TOOLTIP_GAP;
    left = rect.left;
  }

  // If "below"/"right" would push the tooltip off-screen, flip it back inside.
  if (top + TOOLTIP_HEIGHT > vh - pad) top = rect.top - TOOLTIP_HEIGHT - TOOLTIP_GAP;
  if (left + TOOLTIP_WIDTH > vw - pad) left = rect.left - TOOLTIP_WIDTH - TOOLTIP_GAP;

  top = clamp(top, pad, vh - TOOLTIP_HEIGHT - pad);
  left = clamp(left, pad, vw - TOOLTIP_WIDTH - pad);

  const isLast = stepIndex === total - 1;

  return (
    <div
      className="tour-tooltip"
      style={{ top, left }}
      role="dialog"
      aria-label={`Tour step ${stepIndex + 1} of ${total}`}
    >
      <div className="tour-step-label">Step {stepIndex + 1} of {total}</div>
      <div className="tour-title">{cfg.title}</div>
      <div className="tour-body">{cfg.body}</div>
      <div className="tour-actions">
        <button className="tour-skip" onClick={onSkip}>Skip</button>
        <button className="tour-next" onClick={onNext}>{isLast ? "Done →" : "Next →"}</button>
        <div className="tour-dots" aria-hidden="true">
          {Array.from({ length: total }).map((_, i) => (
            <span key={i} className={`tour-dot ${i === stepIndex ? "active" : ""}`} />
          ))}
        </div>
      </div>
    </div>
  );
}

function FinishModal({ onStartFiltering, onDismiss }) {
  return (
    <>
      <div className="tour-overlay" style={{ background: "rgba(0,0,0,0.55)", pointerEvents: "auto" }} />
      <div className="tour-center-modal" role="dialog" aria-label="Tour complete">
        <div className="tour-step-label">Tour complete</div>
        <div className="tour-title">You're all set</div>
        <div className="tour-body">
          Notices refresh nightly. Set your supplier profile to see relevance scores, or start filtering now.
        </div>
        <div className="tour-finish-actions">
          <button className="tour-finish-primary" onClick={onStartFiltering}>Start filtering</button>
          <button className="tour-finish-secondary" onClick={onDismiss}>Maybe later</button>
        </div>
      </div>
    </>
  );
}

export default function Tour({ active, onClose }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [done, setDone] = useState(false);
  const cfg = STEPS[stepIndex];
  const rect = useTargetRect(cfg?.targetId, active && !done);

  // Reset to the first step each time the tour is (re)opened.
  useEffect(() => {
    if (active) { setStepIndex(0); setDone(false); }
  }, [active]);

  // Esc skips the tour.
  useEffect(() => {
    if (!active) return;
    const onKey = (e) => { if (e.key === "Escape") finish(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  if (!active) return null;

  function next() {
    // Skip steps whose target isn't on the page (e.g. empty results table).
    let i = stepIndex + 1;
    while (i < STEPS.length && !document.getElementById(STEPS[i].targetId)) i++;
    if (i < STEPS.length) setStepIndex(i);
    else setDone(true);
  }

  function finish() {
    localStorage.setItem("hasSeenTour", "1");
    onClose();
  }

  function startFiltering() {
    finish();
    setTimeout(() => document.getElementById("kw")?.focus(), 100);
  }

  if (done) {
    return <FinishModal onStartFiltering={startFiltering} onDismiss={finish} />;
  }

  return (
    <div className="tour-overlay">
      {/* Fallback dim so the tour is never invisible, even if the cut-out
          box-shadow gets clipped by an overflow ancestor. */}
      {!rect && <div className="tour-dim" />}
      {rect && (
        <div
          className="tour-highlight"
          style={{
            top: rect.top - 4,
            left: rect.left - 4,
            width: rect.width + 8,
            height: rect.height + 8,
          }}
        />
      )}
      <Tooltip
        cfg={cfg}
        stepIndex={stepIndex}
        total={STEPS.length}
        rect={rect}
        onNext={next}
        onSkip={finish}
      />
      {/* If the target is missing entirely, still show a centered card so the
          user can advance or skip rather than seeing a frozen dim screen. */}
      {!rect && (
        <div className="tour-center-modal" role="dialog" aria-label={`Tour step ${stepIndex + 1}`}>
          <div className="tour-step-label">Step {stepIndex + 1} of {STEPS.length}</div>
          <div className="tour-title">{cfg.title}</div>
          <div className="tour-body">{cfg.body}</div>
          <div className="tour-finish-actions">
            <button className="tour-finish-primary" onClick={next}>Next →</button>
            <button className="tour-finish-secondary" onClick={finish}>Skip</button>
          </div>
        </div>
      )}
    </div>
  );
}
