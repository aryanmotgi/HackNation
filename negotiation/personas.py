"""Customer personas keyed by negotiation_style (matches memory Customer.style).

Each persona drives both the LLM prompt and the offline mock behavior, so the
customer behaves consistently whether or not the API is live.
"""

from __future__ import annotations

# style -> persona spec
PERSONAS: dict[str, dict] = {
    "hard_haggler": {
        "label": "Hard haggler",
        "prompt": (
            "You are a tough procurement buyer. You grind hard on unit price, open "
            "with a lowball well under the quote, concede slowly in small steps, and "
            "name competitor quotes to apply pressure. You only accept when the price "
            "is clearly good for you. You take many rounds."
        ),
        # Mock behavior knobs.
        "open_factor": 0.80,   # first counter as fraction of target price
        "concede_step": 0.06,  # how fast the buyer's willingness rises per round
        "patience": 6,         # rounds before caving
    },
    "responsive": {
        "label": "Responsive buyer",
        "prompt": (
            "You are an easy, relationship-oriented buyer. You are reasonable, respond "
            "warmly, and accept quickly once the price is near fair market. You make at "
            "most one modest counter, then close. You do not drag things out."
        ),
        "open_factor": 0.94,
        "concede_step": 0.10,
        "patience": 2,
    },
    "goes_silent": {
        "label": "Staller",
        "prompt": (
            "You are a non-committal buyer who stalls on price. You are vague, deflect "
            "on numbers, say you need to think or check with others, and rarely make a "
            "firm counter. You do not move."
        ),
        "open_factor": 0.75,
        "concede_step": 0.01,
        "patience": 99,
    },
}


def persona_for(style: str) -> dict:
    """Return the persona spec for a style, defaulting to responsive."""
    return PERSONAS.get(style, PERSONAS["responsive"])
