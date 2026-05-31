const CURRENCY_SYMBOLS = { GBP: "£", EUR: "€", USD: "$" };

/** Compact money: £900k, €1.2M. Falls back to grouped digits below 1000. */
export function fmtValue(value, currency) {
  if (value == null) return "—";
  const sym = CURRENCY_SYMBOLS[currency] || (currency ? `${currency} ` : "");
  const abs = Math.abs(value);
  let n;
  if (abs >= 1_000_000) n = `${(value / 1_000_000).toFixed(1)}M`;
  else if (abs >= 1_000) n = `${Math.round(value / 1_000)}k`;
  else n = Math.round(value).toLocaleString("en-GB");
  return `${sym}${n}`;
}

export function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Whole days from now to the ISO date (negative = past). Null if no date. */
export function daysLeft(iso) {
  if (!iso) return null;
  return Math.floor((new Date(iso) - Date.now()) / 86_400_000);
}

export function fmtCount(n) {
  return (n ?? 0).toLocaleString("en-GB");
}
