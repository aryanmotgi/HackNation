"""Foundation smoke test — run before pushing.

Exercises the whole stack end to end with the offline mock (no API key needed):
memory schema + seed, get_context shapes, escalation, the negotiation loop, code
guardrails, and scoring. Plain asserts, no pytest dependency.

Run:  .venv/bin/python -m tests.smoke   (exit 0 = all good)
"""

from __future__ import annotations

from memory.seed import seed
from memory.retrieve import get_context, write_call, search_patterns
from negotiation.agent import NegotiationAgent
from negotiation.arena import run_session
from negotiation.scoring import price_capture, score_session

PASS = 0


def check(name: str, cond: bool) -> None:
    global PASS
    assert cond, f"FAIL: {name}"
    PASS += 1
    print(f"  ok  {name}")


def main() -> None:
    print("Seeding memory...")
    seed()

    print("\n[memory] get_context shape + content")
    ctx = get_context("cust_alpha")
    for key in ("customer", "open_deal", "past_calls", "winning_tactics", "lookalikes", "escalate"):
        check(f"context has '{key}'", key in ctx)
    check("alpha style is hard_haggler", ctx["customer"]["style"] == "hard_haggler")
    check("alpha floor is 3.2", ctx["open_deal"]["floor_price"] == 3.2)
    check("alpha has lookalike Delta", any(l["name"] == "Delta Fashion" for l in ctx["lookalikes"]))
    check("alpha inherits a lookalike tactic",
          any(t["source"] == "lookalike" for t in ctx["winning_tactics"]))

    print("\n[memory] escalation flag")
    check("charlie escalates (declining history)", get_context("cust_charlie")["escalate"] is True)
    check("bravo does not escalate", get_context("cust_bravo")["escalate"] is False)

    print("\n[memory] unknown customer raises")
    try:
        get_context("nope"); check("unknown raises KeyError", False)
    except KeyError:
        check("unknown raises KeyError", True)

    print("\n[memory] semantic search returns patterns")
    check("search returns results", len(search_patterns("deadline urgency", 2)) > 0)

    print("\n[agent] floor guardrail clamps sub-floor quotes")
    a = NegotiationAgent("cust_alpha")
    a.last_offer = 3.5
    out = a._apply_guardrails(
        {"reasoning": "x", "message": "2.90 final.", "offer_price": 2.90, "intent": "counter"}, "t")
    check("sub-floor 2.90 clamped to floor 3.2", out["offer_price"] == 3.2)
    check("guardrail note recorded", any("clamped" in g for g in out["guardrails"]))

    print("\n[agent] next-step guardrail appends a question")
    out2 = a._apply_guardrails(
        {"reasoning": "x", "message": "Take it or leave it.", "offer_price": 3.9, "intent": "counter"}, "t")
    check("next step appended", "?" in out2["message"])

    print("\n[scoring] boundaries")
    check("capture at floor is 0", price_capture(3.2, 3.2, 4.0) == 0.0)
    check("capture at target is 1", price_capture(4.0, 3.2, 4.0) == 1.0)
    check("escalated scores 0.15",
          score_session(floor=3.2, target=4.0, closed=False, escalated=True,
                        agreed_price=None, best_offer=None, turns=1, max_turns=8)["outcome_score"] == 0.15)

    print("\n[arena] full sessions produce expected results")
    seed()  # clean state
    alpha = run_session("cust_alpha", quiet=True)
    check("alpha closes", alpha["result"] == "closed")
    check("alpha never quotes below floor",
          all(e.get("offer_price") is None or e["offer_price"] >= alpha["floor"]
              for e in alpha["events"] if e["speaker"] == "agent"))
    check("alpha events are structured", len(alpha["events"]) > 0)
    charlie = run_session("cust_charlie", quiet=True)
    check("charlie escalates", charlie["result"] == "escalated")

    print("\n[memory] write_call round-trips")
    seed()
    before = len(get_context("cust_bravo")["past_calls"])
    write_call("cust_bravo", "deal_bravo", "Test call.", 0.5, 0.7, "2026-07-18T12:00:00")
    after = len(get_context("cust_bravo")["past_calls"])
    check("write_call adds a call", after == before + 1)

    print(f"\nALL {PASS} CHECKS PASSED ✓")


if __name__ == "__main__":
    main()
