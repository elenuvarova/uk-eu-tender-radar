import { useEffect, useLayoutEffect, useRef, useState } from "react";

const STEPS = [
  {
    targetId: "tour-stats",
    title: "At a glance",
    body: "Live counts reflecting the current filter state. The red card shows tenders closing this week — act fast on those.",
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
    body: "Sort by closest deadline, most recently published, or highest value. Click an active sort to reverse direction.",
    position: "below",
  },
  {
    targetId: "tour-first-row",
    title: "Open a notice",
    body: "Click any title to read full details in a side panel. UK notices link to Find a Tender; EU notices may open a PDF document on TED.",
    position: "below",
  },
  {
    targetId: "tour-profile",
    title: "Relevance scoring",
    body: "Set your CPV codes and keywords here. Once saved, every notice gets a relevance score (0–100) so the most relevant tenders surface first.",
    position: "right",
  },
];

const TOOLTIP_WIDTH = 300;
const TOOLTIP_GAP = 12;

function useRect(targetId, step) {
  const [rect, setRect] = useState(null);
  useLayoutEffect(() => {
    const el = document.getElementById(targetId);
    if (!el) { setRect(null); return; }
    const r = el.getBoundingClientRect();
    setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
  }, [targetId, step]);
  return rect;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function TooltipPositioned({ step, stepIndex, total, rect, onNext, onSkip }) {
  if (!rect) return null;

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const pad = 16;

  let tooltipTop, tooltipLeft;
  const cfg = STEPS[stepIndex];

  if (cfg.position === "below") {
    tooltipTop = clamp(rect.top + rect.height + TOOLTIP_GAP, pad, vh - 200);
    tooltipLeft = clamp(rect.left + rect.width / 2 - TOOLTIP_WIDTH / 2, pad, vw - TOOLTIP_WIDTH - pad);
  } else if (cfg.position === "right") {
    tooltipTop = clamp(rect.top, pad, vh - 220);
    tooltipLeft = clamp(rect.left + rect.width + TOOLTIP_GAP, pad, vw - TOOLTIP_WIDTH - pad);
  } else {
    tooltipTop = clamp(rect.top - 220 - TOOLTIP_GAP, pad, vh - 220);
    tooltipLeft = clamp(rect.left, pad, vw - TOOLTIP_WIDTH - pad);
  }

  const isLast = stepIndex === total - 1;

  return (
    <div
      className="tour-tooltip"
      style={{ top: tooltipTop, left: tooltipLeft }}
      role="dialog"
      aria-label={`Tour step ${stepIndex + 1} of ${total}`}
    >
      <div className="tour-step-label">Step {stepIndex + 1} of {total}</div>
      <div className="tour-title">{cfg.title}</div>
      <div className="tour-body">{cfg.body}</div>
      <div className="tour-actions">
        <button className="tour-skip" onClick={onSkip}>Skip tour</button>
        <button className="tour-next" onClick={onNext}>
          {isLast ? "Done →" : "Next →"}
        </button>
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
      <div className="tour-overlay" style={{ background: "rgba(0,0,0,0.55)" }} />
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
  const rect = useRect(cfg?.targetId, stepIndex);

  // Reset step when tour is re-opened
  useEffect(() => {
    if (active) { setStepIndex(0); setDone(false); }
  }, [active]);

  // Close on Escape
  useEffect(() => {
    if (!active) return;
    const handler = (e) => { if (e.key === "Escape") finish(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [active]);

  if (!active) return null;

  function next() {
    if (stepIndex < STEPS.length - 1) {
      setStepIndex((i) => i + 1);
    } else {
      setDone(true);
    }
  }

  function finish() {
    localStorage.setItem("hasSeenTour", "1");
    onClose();
  }

  function startFiltering() {
    finish();
    setTimeout(() => {
      document.getElementById("kw")?.focus();
    }, 100);
  }

  if (done) {
    return <FinishModal onStartFiltering={startFiltering} onDismiss={finish} />;
  }

  return (
    <div className="tour-overlay">
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
      <TooltipPositioned
        step={cfg}
        stepIndex={stepIndex}
        total={STEPS.length}
        rect={rect}
        onNext={next}
        onSkip={finish}
      />
    </div>
  );
}
