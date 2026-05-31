export const NOTICE_TYPES = ["PLANNING", "TENDER", "AWARD", "CONTRACT", "MODIFICATION"];

// CLOSED is a synthetic status (OPEN + deadline passed) resolved by the backend;
// it IS filterable — the API maps OPEN/CLOSED to effective status.
export const STATUSES = ["PLANNED", "OPEN", "CLOSED", "AWARDED", "UNSUCCESSFUL", "CANCELLED"];

export const COUNTRIES = [
  ["GB", "United Kingdom"],
  ["DE", "Germany"],
  ["FR", "France"],
  ["BE", "Belgium"],
  ["NL", "Netherlands"],
  ["IE", "Ireland"],
  ["ES", "Spain"],
  ["IT", "Italy"],
  ["PL", "Poland"],
];

// CPV division code -> human label (used in filters and the profile chip picker)
export const CPV_DIVISIONS = [
  ["48", "Software"],
  ["72", "IT services"],
  ["80", "Education & training"],
  ["79", "Business services"],
  ["73", "R&D"],
];

export const CPV_DIVISION_LABELS = Object.fromEntries(CPV_DIVISIONS);

// Suggested keyword chips for first-run profile setup
export const SUGGESTED_KEYWORDS = [
  "cloud",
  "software",
  "digital",
  "data platform",
  "cyber security",
  "e-learning",
  "GDPR",
  "API",
];

// Score bands. The scorer's neutral floor is ~50 (sub-scores default to 0.5),
// so "strong/good/weak" thresholds sit above that floor, not at 0/40/65.
export const SCORE_BANDS = { strong: 70, good: 55 };

export function scoreBand(score) {
  if (score >= SCORE_BANDS.strong) return "strong";
  if (score >= SCORE_BANDS.good) return "good";
  return "weak";
}
