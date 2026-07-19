"""Arena — run the agent against the customer bot, turn by turn.

run_session() drives one negotiation: shows what memory loaded, plays the back-and-
forth (printing the agent's reasoning each turn), scores the result, and writes a
summary back to memory so the learning loop is visible.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from memory.retrieve import write_call

from .agent import NegotiationAgent
from .customer_bot import CustomerBot
from .scoring import score_session

MAX_TURNS = 8

# --- terminal formatting -----------------------------------------------------
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _c(txt: str, color: str) -> str:
    return f"{color}{txt}{RESET}"


def _print_memory_panel(agent: NegotiationAgent) -> None:
    ctx = agent.ctx
    print(_c("┌─ MEMORY LOADED " + "─" * 44, CYAN))
    print(_c("│ ", CYAN) + agent.memory_brief().replace("\n", "\n" + _c("│ ", CYAN)))
    flag = _c("ESCALATE → human", RED) if ctx["escalate"] else _c("clear", GREEN)
    print(_c("│ ", CYAN) + f"Escalation flag: {flag}")
    print(_c("└" + "─" * 60, CYAN))


def _print_agent(turn: dict[str, Any], currency: str) -> None:
    print(_c("  🤖 AGENT", BOLD))
    print("     " + _c("▸ reasoning: " + turn["reasoning"], DIM))
    if turn["offer_price"] is not None:
        print("     " + _c(f"▸ offer: {turn['offer_price']} {currency}", YELLOW))
    for g in turn.get("guardrails", []):
        print("     " + _c("▸ " + g, RED))
    print(f"     says: {turn['message']}")
    print()


def _print_customer(reply: dict[str, Any], label: str) -> None:
    print(_c(f"  🧑 CUSTOMER ({label})", BOLD))
    if reply["counter_price"] is not None:
        print("     " + _c(f"▸ counter: {reply['counter_price']}", YELLOW))
    print(f"     says: {reply['message']}")
    print()


def _transcript_str(lines: list[tuple[str, str]]) -> str:
    return "\n".join(f"{who}: {txt}" for who, txt in lines)


def run_session(customer_id: str, max_turns: int = MAX_TURNS, quiet: bool = False) -> dict[str, Any]:
    """Run one negotiation. Returns a result dict; prints the play-by-play unless quiet."""
    agent = NegotiationAgent(customer_id)
    ctx = agent.ctx
    style = ctx["customer"]["style"]
    from .personas import persona_for
    label = persona_for(style)["label"]

    if not quiet:
        print(_c(f"\n{'='*62}", BOLD))
        print(_c(f" NEGOTIATION — {ctx['customer']['name']}  [{label}]", BOLD))
        print(_c(f"{'='*62}", BOLD))
        _print_memory_panel(agent)
        print()

    lines: list[tuple[str, str]] = []
    events: list[dict[str, Any]] = []  # structured turn log for the frontend
    closed = escalated = walked = False
    agreed_price: Optional[float] = None
    turns = 0

    # Escalation short-circuit: memory says this customer is going bad.
    if ctx["escalate"]:
        t = agent.escalate_turn()
        if not quiet:
            _print_agent(t, agent.currency)
        lines.append(("AGENT", t["message"]))
        events.append(_agent_event(t))
        escalated = True
    else:
        bot = CustomerBot(style, agent.deal["product"], agent.target, agent.currency)
        # Customer opens with interest.
        opening = bot.reply(None, "Hi, I'm interested in your product. What's your price?",
                            _transcript_str(lines))
        lines.append(("CUSTOMER", opening["message"]))
        events.append(_customer_event(opening))
        if not quiet:
            _print_customer(opening, label)
        cust_offer, cust_msg = opening["counter_price"], opening["message"]

        for _ in range(max_turns):
            turns += 1
            at = agent.turn(cust_offer, cust_msg, _transcript_str(lines))
            lines.append(("AGENT", at["message"]))
            events.append(_agent_event(at))
            if not quiet:
                _print_agent(at, agent.currency)

            if at["intent"] == "handoff":
                escalated = True
                break
            if at["intent"] == "accept" and cust_offer is not None and cust_offer >= agent.floor:
                closed, agreed_price = True, cust_offer
                break

            reply = bot.reply(at["offer_price"], at["message"], _transcript_str(lines))
            lines.append(("CUSTOMER", reply["message"]))
            events.append(_customer_event(reply))
            if not quiet:
                _print_customer(reply, label)

            if reply["accepted"] and at["offer_price"] is not None:
                closed, agreed_price = True, at["offer_price"]
                break
            if reply["walked"]:
                walked = True
                break
            cust_offer, cust_msg = reply["counter_price"], reply["message"]

    result = score_session(
        floor=agent.floor, target=agent.target, closed=closed, escalated=escalated,
        agreed_price=agreed_price, best_offer=agent.last_offer,
        turns=turns, max_turns=max_turns,
    )

    # Write the session back to memory (summary, not raw transcript).
    summary = _summarize(ctx["customer"]["name"], agent.deal["product"], result,
                         agreed_price, agent.floor, turns, escalated)
    write_call(
        customer_id=customer_id, deal_id=agent.deal["id"], summary=summary,
        sentiment=result["sentiment"], outcome_score=result["outcome_score"],
        ts=datetime.now().isoformat(timespec="seconds"),
    )

    if not quiet:
        _print_outcome(result, agreed_price, agent.currency, summary)

    return {
        "customer_id": customer_id, "name": ctx["customer"]["name"], "style": style,
        "label": label, "turns": turns, "agreed_price": agreed_price,
        "floor": agent.floor, "target": agent.target, "currency": agent.currency,
        "product": agent.deal["product"],
        "guardrail_hits": len(agent.guardrail_notes),
        "escalate_flag": ctx["escalate"],
        "memory": {
            "style": ctx["customer"]["style"],
            "region": ctx["customer"]["region"],
            "risk_flags": ctx["customer"]["risk_flags"],
            "winning_tactics": ctx["winning_tactics"],
            "lookalikes": ctx["lookalikes"],
            "past_calls": ctx["past_calls"],
        },
        "summary": summary,
        "events": events,
        **result,
    }


def _agent_event(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "speaker": "agent",
        "message": t["message"],
        "reasoning": t.get("reasoning", ""),
        "offer_price": t.get("offer_price"),
        "intent": t.get("intent", "counter"),
        "guardrails": t.get("guardrails", []),
    }


def _customer_event(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "speaker": "customer",
        "message": r["message"],
        "counter_price": r.get("counter_price"),
        "accepted": r.get("accepted", False),
        "walked": r.get("walked", False),
    }


def _summarize(name, product, result, price, floor, turns, escalated) -> str:
    if escalated:
        return f"Escalated to human: {name} ({product}) flagged declining outcomes."
    if result["result"] == "closed":
        return (f"Closed {product} with {name} at {price} (floor {floor}) in {turns} turns; "
                f"price_capture {result['price_capture']}.")
    return f"No deal with {name} on {product} after {turns} turns; held floor {floor}."


def _print_outcome(result, price, currency, summary) -> None:
    r = result["result"]
    color = {"closed": GREEN, "escalated": RED, "no_deal": YELLOW}[r]
    print(_c(f"  ── OUTCOME: {r.upper()} ──", color))
    if price is not None:
        print(f"     price: {price} {currency}   capture: {result['price_capture']}")
    print(f"     outcome_score: {_c(str(result['outcome_score']), color)}   "
          f"sentiment: {result['sentiment']}")
    print("     " + _c("MEMORY UPDATED ▸ " + summary, CYAN))
