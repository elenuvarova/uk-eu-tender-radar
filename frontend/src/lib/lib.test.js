import { describe, it, expect } from "vitest";

import { fmtValue, daysLeft, fmtCount } from "./format";
import { scoreBand, SCORE_BANDS } from "./constants";
import { buildUrl } from "./api";

describe("fmtValue", () => {
  it("formats millions and thousands compactly", () => {
    expect(fmtValue(1_500_000, "EUR")).toBe("€1.5M");
    expect(fmtValue(900_000, "GBP")).toBe("£900k");
  });
  it("groups small numbers and handles null", () => {
    expect(fmtValue(null)).toBe("—");
    expect(fmtValue(0, "EUR")).toBe("€0");
  });
});

describe("scoreBand (C4 — calibrated to the ~50 neutral floor)", () => {
  it("maps scores to strong/good/weak above the neutral floor", () => {
    expect(scoreBand(SCORE_BANDS.strong)).toBe("strong");
    expect(scoreBand(SCORE_BANDS.good)).toBe("good");
    expect(scoreBand(SCORE_BANDS.good - 1)).toBe("weak");
    expect(scoreBand(50)).toBe("weak"); // a neutral-floor notice is NOT "good"
    expect(scoreBand(100)).toBe("strong");
  });
});

describe("buildUrl", () => {
  it("appends array params and skips empty values", () => {
    const url = buildUrl("/api/opportunities", {
      cpv: ["72", "48"],
      q: "",
      source: "UK",
      offset: 0,
    });
    expect(url).toContain("cpv=72");
    expect(url).toContain("cpv=48");
    expect(url).toContain("source=UK");
    expect(url).toContain("offset=0"); // 0 is a real value, kept
    expect(url).not.toContain("q=");
  });
});

describe("daysLeft", () => {
  it("returns null for no date and floors the day difference", () => {
    expect(daysLeft(null)).toBe(null);
    const inTwoDays = new Date(Date.now() + 2 * 86_400_000 + 3_600_000).toISOString();
    expect(daysLeft(inTwoDays)).toBe(2);
  });
});

describe("fmtCount", () => {
  it("groups thousands and treats null as 0", () => {
    expect(fmtCount(1234)).toBe("1,234");
    expect(fmtCount(null)).toBe("0");
  });
});
