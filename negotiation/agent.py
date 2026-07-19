"""Negotiation agent — negotiates for the manufacturer, adapting from memory.

Before negotiating it calls get_context(customer_id) and builds its system prompt
from what memory returns (style, floor price, winning tactics, lookalikes, history).
Guardrails are enforced in CODE, not left to the model:

  * never quote below the deal's floor price          (clamped after the model replies)
  * always propose a next step                        (appended if missing)
  * if memory flags escalation -> hand off to a human (no autonomous negotiation)

Each turn emits the agent's reasoning AND its offer, so the transcript shows the
agent thinking, not reading a script.
"""

from __future__ import annotations

from typing import Any, Optional

from memory.retrieve import get_context

from .llm import complete_json

# Agent response contract (JSON):
#   reasoning:   str            why this move — should reference memory
#   message:     str            what the agent says to the customer
#   offer_price: float | null   the per-unit price being quoted this turn
#   intent:      "counter" | "accept" | "handoff" | "hold"

NEXT_STEP_HINT = "What volume are you locking in, so I can firm this up today?"


class NegotiationAgent:
    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        self.ctx = get_context(customer_id)
        self.deal = self.ctx["open_deal"]
        if self.deal is None:
            raise ValueError(f"No open deal for {customer_id}")
        self.floor = float(self.deal["floor_price"])
        self.target = float(self.deal["target_price"])
        self.currency = self.deal["currency"]
        self.last_offer: Optional[float] = None
        self.guardrail_notes: list[str] = []

    # --- memory-derived context the agent negotiates from ---
    def memory_brief(self) -> str:
        c = self.ctx["customer"]
        tactics = ", ".join(
            f"{t['label']} ({t['source']})" for t in self.ctx["winning_tactics"]
        ) or "none recorded"
        looks = ", ".join(l["name"] for l in self.ctx["lookalikes"]) or "none"
        recent = "; ".join(
            f"{r['ts'][:10]} score={r['outcome_score']}" for r in self.ctx["past_calls"]
        ) or "no history"
        return (
            f"Customer: {c['name']} ({c['style']}), region {c['region']}, "
            f"risk_flags={c['risk_flags']}.\n"
            f"Deal: {self.deal['product']} | floor {self.floor} {self.currency} "
            f"(NEVER quote below) | target {self.target} {self.currency}.\n"
            f"Tactics that have worked: {tactics}.\n"
            f"Lookalike customers: {looks}.\n"
            f"Recent call outcomes: {recent}."
        )

    def _system(self) -> str:
        return (
            "You are an expert sales negotiator for a clothing manufacturer. You sell "
            "TO buyers, so a HIGHER unit price is better for you. Use the memory brief "
            "to adapt: press hard hagglers with proven tactics, close responsive buyers "
            "quickly, protect margin. NEVER quote below the floor price.\n\n"
            f"MEMORY BRIEF:\n{self.memory_brief()}\n\n"
            "Each turn respond ONLY as JSON: {\"reasoning\": str, \"message\": str, "
            "\"offer_price\": number|null, \"intent\": \"counter\"|\"accept\"|\"hold\"|\"handoff\"}. "
            "reasoning must cite the memory (style, tactic, or history) you are acting on. "
            "message is 1-3 sentences to the buyer and should end by proposing a next step. "
            "Set intent=accept only to accept the buyer's stated counter."
        )

    def _user(self, customer_offer: Optional[float], customer_message: str, transcript: str) -> str:
        return (
            f"Conversation so far:\n{transcript or '(none)'}\n\n"
            f"Buyer just said: \"{customer_message}\"\n"
            f"Buyer's current counter: {customer_offer if customer_offer is not None else 'none'}\n"
            f"Your last offer: {self.last_offer if self.last_offer is not None else 'none'}\n"
            "Make your move as JSON."
        )

    # --- offline mock: concede from above target toward the floor, never below ---
    def _mock(self, customer_offer: Optional[float]) -> dict[str, Any]:
        style = self.ctx["customer"]["style"]
        if self.last_offer is None:
            offer = round(self.target * 1.08, 2)  # anchor high
            tac = self.ctx["winning_tactics"][0]["label"] if self.ctx["winning_tactics"] else "anchoring"
            return {"reasoning": f"Opening high to anchor; {style} responds to firm framing. Leaning on '{tac}'.",
                    "message": f"For {self.deal['product']} I can do {offer} {self.currency} per unit.",
                    "offer_price": offer, "intent": "counter"}
        # Accept a buyer counter that is at/above floor and reasonably close to target.
        if customer_offer is not None and customer_offer >= self.floor and customer_offer >= self.target * 0.9:
            return {"reasoning": f"Buyer's {customer_offer} clears floor and is near target — lock it in.",
                    "message": f"Deal at {customer_offer} {self.currency} per unit. I'll send the PO.",
                    "offer_price": customer_offer, "intent": "accept"}
        # Otherwise concede a small step toward the floor.
        step = (self.last_offer - self.floor) * 0.35
        offer = round(max(self.floor, self.last_offer - step), 2)
        return {"reasoning": f"Conceding a small step to {offer}, holding well above floor {self.floor}.",
                "message": f"I can come to {offer} {self.currency} per unit if we close today.",
                "offer_price": offer, "intent": "counter"}

    def escalate_turn(self) -> dict[str, Any]:
        """Immediate human handoff — used when memory flags declining outcomes."""
        c = self.ctx["customer"]
        scores = [r["outcome_score"] for r in self.ctx["past_calls"]]
        return {
            "reasoning": f"Memory shows declining outcomes for {c['name']} ({scores}). "
                         "Policy: do not negotiate autonomously — escalate to a human.",
            "message": f"I want to make sure we get this right — let me bring in our accounts "
                       f"lead to work through {self.deal['product']} with you directly.",
            "offer_price": None,
            "intent": "handoff",
            "source": "policy",
        }

    def turn(self, customer_offer: Optional[float], customer_message: str, transcript: str) -> dict[str, Any]:
        data, source = complete_json(
            self._system(),
            self._user(customer_offer, customer_message, transcript),
            mock=lambda: self._mock(customer_offer),
        )
        return self._apply_guardrails(data, source)

    # --- code-enforced guardrails ---
    def _apply_guardrails(self, data: dict[str, Any], source: str) -> dict[str, Any]:
        reasoning = str(data.get("reasoning", "")).strip()
        message = str(data.get("message", "")).strip() or "(...)"
        intent = data.get("intent", "counter")
        offer = _as_float(data.get("offer_price"))
        notes: list[str] = []

        # Floor guardrail: clamp any sub-floor quote up to the floor.
        if offer is not None and offer < self.floor:
            notes.append(f"GUARDRAIL: model tried {offer} < floor {self.floor}; clamped to floor.")
            offer = self.floor
            message = f"The best I can responsibly do is {self.floor} {self.currency} per unit."

        # Next-step guardrail: counters/holds must propose a next step.
        if intent in ("counter", "hold") and "?" not in message:
            message = f"{message} {NEXT_STEP_HINT}"
            notes.append("GUARDRAIL: appended a next step.")

        if intent == "counter" and offer is not None:
            self.last_offer = offer

        self.guardrail_notes.extend(notes)
        return {
            "reasoning": reasoning,
            "message": message,
            "offer_price": offer,
            "intent": intent,
            "guardrails": notes,
            "source": source,
        }


def _as_float(v) -> Optional[float]:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None
