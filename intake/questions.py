"""Deterministic hard-rule question engine — NO LLM.

Pure code looks at the parsed draft and returns a fixed, scripted set of questions:
gap-fill questions (only when the PDF didn't provide the field) plus always-ask
guardrail questions. Predictable and auditable — the same draft always yields the
same questions.

    questions_for(draft) -> list[question]
    apply_answers(draft, answers) -> (deal, hard_rules, question_audit)
"""

from __future__ import annotations

from typing import Any

# type: "number" | "text" | "list"
# ask_if: "missing" (only when draft lacks the field) | "always"
QUESTIONS = [
    {
        "id": "floor_price", "field": "deal", "type": "number", "ask_if": "missing",
        "prompt": "What's your absolute floor price per unit? (the agent will NEVER go below this)",
    },
    {
        "id": "target_price", "field": "deal", "type": "number", "ask_if": "missing",
        "prompt": "What's your target price per unit? (what you'd like to close at)",
    },
    {
        "id": "forbidden_terms", "field": "hard_rules", "type": "list", "ask_if": "always",
        "prompt": "Any terms you'll never agree to? (comma-separated, e.g. exclusivity, consignment)",
    },
    {
        "id": "walk_away_price", "field": "hard_rules", "type": "number", "ask_if": "always",
        "prompt": "Walk-away point — price per unit below which the agent should end the deal? (optional)",
    },
    {
        "id": "escalation_trigger", "field": "hard_rules", "type": "text", "ask_if": "always",
        "prompt": "When should this escalate to a human? (e.g. 'declining calls' or 'payment dispute')",
    },
]


def questions_for(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the scripted questions to ask for this draft.

    'missing' questions are skipped when the PDF already supplied the field.
    """
    out = []
    for q in QUESTIONS:
        if q["ask_if"] == "missing" and draft.get(q["id"]) not in (None, ""):
            continue  # PDF already gave us this — don't ask
        out.append({
            "id": q["id"], "type": q["type"], "prompt": q["prompt"],
            "field": q["field"],
        })
    return out


def _coerce(qtype: str, raw: Any) -> Any:
    if raw is None or raw == "":
        return [] if qtype == "list" else None
    if qtype == "number":
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    if qtype == "list":
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
        return [t.strip() for t in str(raw).split(",") if t.strip()]
    return str(raw).strip()


def apply_answers(
    draft: dict[str, Any], answers: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Merge PDF draft + question answers into (deal, hard_rules, audit trail).

    `answers` maps question id -> raw answer. Each answered field is tagged with
    its source (pdf | user) in the returned audit list.
    """
    deal = {
        "product": draft.get("product"),
        "quantity": draft.get("quantity"),
        "unit": draft.get("unit", "units"),
        "floor_price": draft.get("floor_price"),
        "target_price": draft.get("target_price"),
        "currency": draft.get("currency") or "USD",
        "payment_terms": draft.get("payment_terms"),
    }
    hard_rules: dict[str, Any] = {
        "forbidden_terms": [],
        "walk_away_price": None,
        "escalation_trigger": "",
        "always_propose_next_step": True,
    }
    audit: list[dict[str, Any]] = []

    by_id = {q["id"]: q for q in QUESTIONS}
    for qid, q in by_id.items():
        if qid in answers and answers[qid] not in (None, ""):
            value = _coerce(q["type"], answers[qid])
            source = "user"
        elif q["field"] == "deal" and deal.get(qid) is not None:
            value = deal.get(qid)
            source = "pdf"
        else:
            continue
        target = deal if q["field"] == "deal" else hard_rules
        target[qid] = value
        audit.append({"id": qid, "prompt": q["prompt"], "answer": value, "source": source})

    return deal, hard_rules, audit
