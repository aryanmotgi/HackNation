"""Session scoring — turns a negotiation into an outcome_score in [0, 1].

Higher is better FOR THE MANUFACTURER. Three signals drive it:

  price_capture  where the closing price landed between floor and target.
                 0.0 at the floor, 1.0 at (or above) the target. This is the main
                 driver — holding margin is the point.
  close bonus    a flat reward for actually closing a deal (a walk-away is worse
                 than a mediocre close).
  speed          fewer turns is better; grinding costs time and goodwill.

Special cases:
  escalated -> 0.15  (handed to a human; not a win, not a total loss)
  no deal   -> up to 0.30 * price_capture on the best offer reached (partial credit)

The score written back to memory is what makes the escalation logic work: a run of
declining scores is exactly what get_context() flags for human handoff next time.
"""

from __future__ import annotations

CLOSE_BONUS = 0.25
PRICE_WEIGHT = 0.60
SPEED_WEIGHT = 0.15


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def price_capture(price: float, floor: float, target: float) -> float:
    """0.0 at floor, 1.0 at/above target."""
    if target <= floor:
        return 1.0
    return _clamp((price - floor) / (target - floor))


def score_session(
    *,
    floor: float,
    target: float,
    closed: bool,
    escalated: bool,
    agreed_price: float | None,
    best_offer: float | None,
    turns: int,
    max_turns: int,
) -> dict:
    """Return {outcome_score, sentiment, result, price_capture}."""
    if escalated:
        return {"outcome_score": 0.15, "sentiment": -0.5,
                "result": "escalated", "price_capture": 0.0}

    if closed and agreed_price is not None:
        capture = price_capture(agreed_price, floor, target)
        speed = _clamp(1 - (turns - 2) / max(1, max_turns - 2))
        score = round(PRICE_WEIGHT * capture + CLOSE_BONUS + SPEED_WEIGHT * speed, 2)
        return {"outcome_score": score, "sentiment": round(0.3 + 0.4 * capture, 2),
                "result": "closed", "price_capture": round(capture, 2)}

    # No deal — partial credit for how far the agent pushed the best offer.
    capture = price_capture(best_offer, floor, target) if best_offer is not None else 0.0
    return {"outcome_score": round(0.30 * capture, 2), "sentiment": -0.2,
            "result": "no_deal", "price_capture": round(capture, 2)}
