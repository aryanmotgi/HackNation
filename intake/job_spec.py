"""Job spec (v2) — build, validate, save, and load the intake → negotiation contract.

The intake wizard (Company · Catalog · Guardrails · Voice · Test) produces one JSON
artifact per job: jobs/<job_id>.json. The agent negotiates ONLY a confirmed spec;
`load_job_spec` refuses drafts. `validate_spec` enforces numeric sanity so a bad PDF
parse can never reach the agent.

v2 adds company{} (step 1), an extended deal{} (step 2), richer hard_rules{} +
escalation toggles (step 3), and voice{} (step 4, stubbed). New fields are additive
— negotiation still reads deal + hard_rules exactly as before.

See schemas/job_spec.md for the full field reference.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

JOBS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jobs")

# Canonical escalation triggers (Guardrails toggles). Order is display order.
ESCALATION_TRIGGERS = [
    "price_below_floor",
    "unsupported_customization",
    "angry_or_manager",
    "order_exceeds_transfer_limit",
]


class DraftSpecError(Exception):
    """Raised when something tries to negotiate a non-confirmed spec."""


def _num(v: Any) -> Optional[float]:
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> Optional[int]:
    n = _num(v)
    return None if n is None else int(n)


def build_job_spec(
    *,
    deal: dict[str, Any],
    hard_rules: dict[str, Any],
    questions: list[dict[str, Any]] | None = None,
    source: str = "pdf",
    created_at: str,
    status: str = "confirmed",
    company: dict[str, Any] | None = None,
    voice: dict[str, Any] | None = None,
    job_id: Optional[str] = None,
) -> dict[str, Any]:
    """Assemble a v2 job spec. Mirrors deal.floor_price into hard_rules.floor_price."""
    company = company or {}
    voice = voice or {}
    questions = questions or []

    product = deal.get("product") or "job"
    slug = re.sub(r"[^a-z0-9]+", "_", str(product).lower()).strip("_") or "job"
    jid = job_id or f"job_{slug}_{created_at[:10].replace('-', '')}"

    floor = _num(deal.get("floor_price"))

    return {
        "job_id": jid,
        "created_at": created_at,
        "source": source,
        "status": status,
        "company": {
            "name": company.get("name"),
            "website": company.get("website"),
            "location": company.get("location"),
            "timezone": company.get("timezone"),
            "languages": company.get("languages") or [],
            "sales_hours": company.get("sales_hours"),
        },
        "deal": {
            "product": deal.get("product"),
            "sku": deal.get("sku"),
            "quantity": _int(deal.get("quantity")),
            "unit": deal.get("unit", "units"),
            "opening_price": _num(deal.get("opening_price")),
            "target_price": _num(deal.get("target_price")),
            "floor_price": floor,
            "currency": deal.get("currency", "USD"),
            "volume_tiers": deal.get("volume_tiers") or [],
            "lead_time_days": _int(deal.get("lead_time_days")),
            "payment_terms": deal.get("payment_terms"),
            "shipping_terms": deal.get("shipping_terms"),
        },
        "hard_rules": {
            "floor_price": floor,  # mirrors the deal floor — the ENFORCED floor
            "forbidden_terms": hard_rules.get("forbidden_terms") or [],
            "walk_away_price": _num(hard_rules.get("walk_away_price")),
            "require_approval_below": _num(hard_rules.get("require_approval_below")),
            "transfer_deals_above": _num(hard_rules.get("transfer_deals_above")),
            "escalation_triggers": [
                t for t in (hard_rules.get("escalation_triggers") or []) if t in ESCALATION_TRIGGERS
            ],
            "always_propose_next_step": bool(hard_rules.get("always_propose_next_step", True)),
        },
        "voice": {
            "agent_name": voice.get("agent_name"),
            "phone": voice.get("phone"),
            "voice_style": voice.get("voice_style"),
            "elevenlabs_agent_id": voice.get("elevenlabs_agent_id"),  # wired server-side later
        },
        "questions": questions,
    }


def validate_spec(spec: dict[str, Any]) -> list[str]:
    """Return human-readable problems. Empty = valid. Catches bad parses pre-confirm."""
    errors: list[str] = []
    deal = spec.get("deal", {}) or {}
    hr = spec.get("hard_rules", {}) or {}

    if not (deal.get("product") and str(deal["product"]).strip()):
        errors.append("Product is missing.")

    qty = deal.get("quantity")
    if not isinstance(qty, (int, float)) or qty is None or qty <= 0:
        errors.append("Minimum order (quantity) must be a number greater than 0.")

    floor = deal.get("floor_price")
    target = deal.get("target_price")
    if not isinstance(floor, (int, float)) or floor is None or floor <= 0:
        errors.append("Hard floor price must be a number greater than 0.")
    if not isinstance(target, (int, float)) or target is None or target <= 0:
        errors.append("Target price must be a number greater than 0.")
    if isinstance(floor, (int, float)) and isinstance(target, (int, float)) and target < floor:
        errors.append(f"Target price ({target}) must be at or above the hard floor ({floor}).")

    opening = deal.get("opening_price")
    if isinstance(opening, (int, float)) and isinstance(floor, (int, float)) and opening < floor:
        errors.append(f"Opening price ({opening}) should be at or above the hard floor ({floor}).")

    if isinstance(floor, (int, float)) and hr.get("floor_price") != floor:
        errors.append("Hard-rule floor must equal the deal hard floor.")

    walk = hr.get("walk_away_price")
    if walk is not None:
        if not isinstance(walk, (int, float)):
            errors.append("Walk-away price must be a number or empty.")
        elif isinstance(floor, (int, float)) and walk > floor:
            errors.append(f"Walk-away price ({walk}) should be at or below the floor ({floor}).")

    for key, label in (("require_approval_below", "Require-approval-below"),
                       ("transfer_deals_above", "Transfer-deals-above")):
        v = hr.get(key)
        if v is not None and (not isinstance(v, (int, float)) or v < 0):
            errors.append(f"{label} must be a number or empty.")

    if not isinstance(hr.get("forbidden_terms", []), list):
        errors.append("Forbidden terms must be a list.")
    if not isinstance(hr.get("escalation_triggers", []), list):
        errors.append("Escalation triggers must be a list.")

    return errors


def save_job_spec(spec: dict[str, Any], jobs_dir: str = JOBS_DIR) -> str:
    os.makedirs(jobs_dir, exist_ok=True)
    path = os.path.join(jobs_dir, f"{spec['job_id']}.json")
    with open(path, "w") as f:
        json.dump(spec, f, indent=2)
    return path


def load_job_spec(path: str) -> dict[str, Any]:
    """Load a job spec for the agent. Refuses drafts and invalid specs."""
    with open(path) as f:
        spec = json.load(f)
    if spec.get("status") != "confirmed":
        raise DraftSpecError(
            f"Refusing to negotiate '{spec.get('job_id')}': status is "
            f"'{spec.get('status')}', not 'confirmed'."
        )
    errors = validate_spec(spec)
    if errors:
        raise ValueError(f"Invalid job spec '{spec.get('job_id')}': {'; '.join(errors)}")
    return spec
