"""Scoring weights config — edit here to re-tune without touching logic."""

SCORE_WEIGHTS = {
    "cpv":      0.35,
    "keyword":  0.25,
    "value":    0.15,
    "deadline": 0.15,
    "buyer":    0.10,
}

assert abs(sum(SCORE_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1"
