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

// Extended map covering all common CPV divisions that appear in procurement data.
// Used to translate raw division codes to readable labels in charts.
export const CPV_DIVISION_LABELS = {
  ...Object.fromEntries(CPV_DIVISIONS),
  "30": "Office & computer equipment",
  "32": "Communications equipment",
  "33": "Medical equipment",
  "34": "Transport equipment",
  "35": "Security equipment",
  "38": "Laboratory equipment",
  "42": "Industrial machinery",
  "45": "Construction",
  "50": "Maintenance & repair",
  "51": "Installation services",
  "55": "Hotel & restaurant services",
  "60": "Transport services",
  "64": "Telecommunications",
  "66": "Financial services",
  "71": "Engineering & consulting",
  "75": "Public administration",
  "76": "Services to oil/gas industry",
  "77": "Agricultural services",
  "85": "Health services",
  "90": "Environmental services",
  "92": "Cultural & sporting services",
  "98": "Other community services",
};

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
