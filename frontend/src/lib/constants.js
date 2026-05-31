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
// Display label for a country code. GB → "UK" so the country column matches the
// "UK" source badge (Find a Tender covers the whole United Kingdom); every other
// ISO code is shown as-is. Keeps the data layer on ISO codes for filtering.
const COUNTRY_DISPLAY = { GB: "UK" };
export function displayCountry(code) {
  if (!code) return "—";
  return COUNTRY_DISPLAY[code] || code;
}

export const CPV_DIVISION_LABELS = {
  ...Object.fromEntries(CPV_DIVISIONS),
  "03": "Agriculture & forestry products",
  "09": "Fuels & electricity",
  "14": "Mining & metals",
  "15": "Food & beverages",
  "16": "Agricultural machinery",
  "18": "Clothing & footwear",
  "19": "Textiles & plastics",
  "22": "Printed matter",
  "24": "Chemicals",
  "30": "Office & computer equipment",
  "31": "Electrical machinery",
  "32": "Communications equipment",
  "33": "Medical equipment",
  "37": "Musical & sports goods",
  "39": "Furniture & furnishings",
  "41": "Water",
  "43": "Construction machinery",
  "44": "Construction materials",
  "63": "Supporting transport services",
  "65": "Public utilities",
  "70": "Real estate services",
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
