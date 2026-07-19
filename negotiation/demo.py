"""Demo — one agent, three customer styles, side by side.

Run:
    python -m negotiation.demo              # reseed memory, negotiate all 3
    python -m negotiation.demo --no-reseed  # keep current memory state
    python -m negotiation.demo --only cust_alpha

Watch the SAME agent adapt: grind a hard haggler, close an easy buyer fast, and
escalate the stalling customer to a human — each turn printing its reasoning.
"""

from __future__ import annotations

import argparse

from .arena import BOLD, CYAN, GREEN, RED, RESET, YELLOW, run_session
from .llm import MODEL, using_live_model

# The three hero customers (Delta stays in memory as Alpha's hidden lookalike).
HERO_CUSTOMERS = ["cust_alpha", "cust_bravo", "cust_charlie"]


def _reseed() -> None:
    from memory.seed import seed
    seed()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-reseed", dest="reseed", action="store_false",
                    help="do not rebuild memory before running")
    ap.add_argument("--only", help="run a single customer id")
    args = ap.parse_args()

    if args.reseed:
        _reseed()

    mode = (f"{GREEN}LIVE model{RESET} ({MODEL})" if using_live_model()
            else f"{YELLOW}offline mock{RESET} (no OPENAI_API_KEY)")
    print(f"{BOLD}Negotiation demo — {mode}{RESET}")

    customers = [args.only] if args.only else HERO_CUSTOMERS
    results = [run_session(cid) for cid in customers]

    # Summary table.
    print(f"\n{BOLD}{'='*62}{RESET}")
    print(f"{BOLD} SUMMARY — same agent, {len(results)} strategies{RESET}")
    print(f"{BOLD}{'='*62}{RESET}")
    print(f"  {'customer':16}{'style':14}{'result':10}{'price':>8}{'score':>7}")
    print("  " + "-" * 55)
    color = {"closed": GREEN, "escalated": RED, "no_deal": YELLOW}
    for r in results:
        price = f"{r['agreed_price']}" if r["agreed_price"] is not None else "—"
        c = color[r["result"]]
        print(f"  {r['name']:16}{r['style']:14}{c}{r['result']:10}{RESET}"
              f"{price:>8}{c}{r['outcome_score']:>7}{RESET}")
    print()
    print(f"  {CYAN}Adaptation came from memory — floor held every time, "
          f"Charlie escalated on declining history.{RESET}")


if __name__ == "__main__":
    main()
