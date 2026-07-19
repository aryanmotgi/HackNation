"""Customer bot — an LLM playing a buyer persona so the agent has an opponent.

The bot knows the product and its own willingness-to-pay, but NOT the manufacturer's
floor price. It replies in character each turn and signals accept / counter / walk.
"""

from __future__ import annotations

from typing import Any, Optional

from .llm import complete_json
from .personas import persona_for

# Customer response contract (JSON):
#   message:       str            what the buyer says
#   counter_price: float | null   price the buyer proposes (per unit), if any
#   accepted:      bool           accepts the agent's current offer
#   walked:        bool           ends the negotiation with no deal


class CustomerBot:
    def __init__(self, style: str, product: str, target_price: float, currency: str):
        self.style = style
        self.persona = persona_for(style)
        self.product = product
        self.target_price = target_price   # the agent's target = a price the buyer resists
        self.currency = currency
        self._turn = 0  # buyer replies so far (drives mock concession)

    # --- prompt for the live model ---
    def _system(self) -> str:
        return (
            f"{self.persona['prompt']}\n\n"
            f"You are buying: {self.product}. Quotes are per unit in {self.currency}. "
            "Stay in character. Keep replies to 1-3 sentences.\n"
            "Respond ONLY as JSON: {\"message\": str, \"counter_price\": number|null, "
            "\"accepted\": bool, \"walked\": bool}. Set accepted=true only when you "
            "genuinely accept the agent's latest offer."
        )

    def _user(self, agent_offer: Optional[float], agent_message: str, transcript: str) -> str:
        return (
            f"Conversation so far:\n{transcript or '(none)'}\n\n"
            f"The seller just said: \"{agent_message}\"\n"
            f"Their current offer: {agent_offer if agent_offer is not None else 'none yet'}\n"
            "Reply in character as JSON."
        )

    # --- offline mock: deterministic, persona-shaped ---
    def _mock(self, agent_offer: Optional[float]) -> dict[str, Any]:
        p = self.persona
        # Buyer's willingness rises from open_factor toward (and past) target over turns.
        willing = self.target_price * min(
            1.05, p["open_factor"] + p["concede_step"] * self._turn
        )
        counter = round(willing, 2)

        if self.style == "goes_silent":
            return {"message": "Hmm, let me take this back to my team and think it over.",
                    "counter_price": None, "accepted": False, "walked": False}

        # Accept when the seller's offer has come down to what the buyer will pay,
        # or the buyer is out of patience.
        if agent_offer is not None and (agent_offer <= willing or self._turn >= p["patience"]):
            return {"message": f"Alright, at {agent_offer} {self.currency} per unit, you have a deal.",
                    "counter_price": None, "accepted": True, "walked": False}

        if self.style == "responsive":
            return {"message": f"That's a little high. Meet me at {counter} and I'm in.",
                    "counter_price": counter, "accepted": False, "walked": False}

        # hard_haggler: keep pushing, cite competition
        return {"message": f"Too steep. I've got another supplier near {counter}. Do better.",
                "counter_price": counter, "accepted": False, "walked": False}

    def reply(self, agent_offer: Optional[float], agent_message: str, transcript: str) -> dict[str, Any]:
        data, source = complete_json(
            self._system(),
            self._user(agent_offer, agent_message, transcript),
            mock=lambda: self._mock(agent_offer),
        )
        self._turn += 1
        # Normalize / guard the fields the arena relies on.
        return {
            "message": str(data.get("message", "")).strip() or "(...)",
            "counter_price": _as_float(data.get("counter_price")),
            "accepted": bool(data.get("accepted", False)),
            "walked": bool(data.get("walked", False)),
            "source": source,
        }


def _as_float(v) -> Optional[float]:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None
