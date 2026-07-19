"""Job spec — build, validate, save, and load the intake → negotiation contract.

The agent negotiates ONLY a confirmed spec. `load_job_spec` refuses drafts.
`validate_spec` enforces the numeric sanity rules so a bad PDF parse can never
reach the agent (floor > 0, quantity > 0, floor <= target, etc.).

See schemas/job_spec.md for the full field reference.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

JOBS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jobs")


class DraftSpecError(Exception):
    """Raised when something tries to negotiate a non-confirmed spec."""


def build_job_spec(
    *,
    deal: dict[str, Any],
    hard_rules: dict[str, Any],
    questions: list[dict[str, Any]],
    source: str,
    created_at: str,
    status: str = "confirmed",
    job_id: Optional[str] = None,
) -> dict[str, Any]:
    """Assemble a job spec dict. Mirrors deal.floor_price into hard_rules."""
    product = deal.get("product") or "job"
    slug = re.sub(r"[^a-z0-9]+", "_", str(product).lower()).strip("_") or "job"
    jid = job_id or f"job_{slug}_{created_at[:10].replace('-', '')}"

    hr = dict(hard_rules)
    hr["floor_price"] = deal.get("floor_price")  # hard_rules floor mirrors the deal floor
    hr.setdefault("forbidden_terms", [])
    hr.setdefault("walk_away_price", None)
    hr.setdefault("escalation_trigger", "")
    hr.setdefault("always_propose_next_step", True)

    return {
        "job_id": jid,
        "created_at": created_at,
        "source": source,
        "status": status,
        "deal": {
            "product": deal.get("product"),
            "quantity": deal.get("quantity"),
            "unit": deal.get("unit", "units"),
            "floor_price": deal.get("floor_price"),
            "target_price": deal.get("target_price"),
            "currency": deal.get("currency", "USD"),
            "payment_terms": deal.get("payment_terms"),
        },
        "hard_rules": hr,
        "questions": questions,
    }


def validate_spec(spec: dict[str, Any]) -> list[str]:
    """Return a list of human-readable problems. Empty list = valid.

    Catches bad parses BEFORE confirmation so the agent never negotiates garbage.
    """
    errors: list[str] = []
    deal = spec.get("deal", {}) or {}
    hr = spec.get("hard_rules", {}) or {}

    product = deal.get("product")
    if not product or not str(product).strip():
        errors.append("Product is missing.")

    qty = deal.get("quantity")
    if not isinstance(qty, (int, float)) or qty is None or qty <= 0:
        errors.append("Quantity must be a number greater than 0.")

    floor = deal.get("floor_price")
    target = deal.get("target_price")
    if not isinstance(floor, (int, float)) or floor is None or floor <= 0:
        errors.append("Floor price must be a number greater than 0.")
    if not isinstance(target, (int, float)) or target is None or target <= 0:
        errors.append("Target price must be a number greater than 0.")
    if isinstance(floor, (int, float)) and isinstance(target, (int, float)) and target < floor:
        errors.append(f"Target price ({target}) must be greater than or equal to floor ({floor}).")

    # hard_rules floor must mirror the deal floor
    if isinstance(floor, (int, float)) and hr.get("floor_price") != floor:
        errors.append("Hard-rule floor must equal the deal floor price.")

    walk = hr.get("walk_away_price")
    if walk is not None:
        if not isinstance(walk, (int, float)):
            errors.append("Walk-away price must be a number or empty.")
        elif isinstance(floor, (int, float)) and walk > floor:
            errors.append(f"Walk-away price ({walk}) should be at or below the floor ({floor}).")

    if not isinstance(hr.get("forbidden_terms", []), list):
        errors.append("Forbidden terms must be a list.")

    return errors


def save_job_spec(spec: dict[str, Any], jobs_dir: str = JOBS_DIR) -> str:
    """Write the spec to jobs/<job_id>.json and return the path."""
    os.makedirs(jobs_dir, exist_ok=True)
    path = os.path.join(jobs_dir, f"{spec['job_id']}.json")
    with open(path, "w") as f:
        json.dump(spec, f, indent=2)
    return path


def load_job_spec(path: str) -> dict[str, Any]:
    """Load a job spec for the agent. Refuses drafts and invalid specs.

    Raises:
        DraftSpecError  if status != "confirmed"
        ValueError      if the spec fails validation
    """
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
