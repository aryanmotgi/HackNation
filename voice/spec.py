"""Job-spec loading + per-call prompt building.

The confirmed job spec (from the intake wizard, jobs/<id>.json) is the manufacturer's
pricing + guardrails, reused verbatim on every call. build_system_prompt() fuses that
spec with the caller's memory (get_context) into the system prompt the ElevenLabs agent
runs for this specific call — so the SAME confirmed spec drives every conversation.
"""

from __future__ import annotations

import glob
import json
import os
import re
from typing import Any, Optional

from intake.job_spec import JOBS_DIR, validate_spec

# Fallback spec so the service works before any intake spec is confirmed. Mirrors
# the demo product the ElevenLabs agent was seeded with (cotton tees, 3.20/4.00).
FALLBACK_SPEC: dict[str, Any] = {
    "job_id": "job_fallback_cotton",
    "status": "confirmed",
    "company": {"name": "Loomhaus", "location": "Shenzhen"},
    "deal": {
        "product": "Cotton T-shirts", "quantity": 10000, "unit": "units",
        "opening_price": 4.40, "target_price": 4.00, "floor_price": 3.20,
        "currency": "USD", "payment_terms": "net-30",
    },
    "hard_rules": {
        "floor_price": 3.20, "forbidden_terms": ["exclusivity", "consignment"],
        "walk_away_price": None, "transfer_deals_above": None,
        "escalation_triggers": ["price_below_floor", "angry_or_manager"],
        "always_propose_next_step": True,
    },
}


def load_active_spec(jobs_dir: str = JOBS_DIR) -> dict[str, Any]:
    """Return the most-recently-created confirmed job spec, or the fallback.

    Scans jobs/*.json, keeps only status=='confirmed' and structurally valid specs,
    and returns the newest by created_at. Guarantees the agent always has a valid,
    confirmed spec to negotiate against.
    """
    best: Optional[dict[str, Any]] = None
    for path in glob.glob(os.path.join(jobs_dir, "*.json")):
        try:
            with open(path) as f:
                spec = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if spec.get("status") != "confirmed" or validate_spec(spec):
            continue
        if best is None or (spec.get("created_at", "") > best.get("created_at", "")):
            best = spec
    return best or FALLBACK_SPEC


def memory_brief(ctx: dict[str, Any]) -> str:
    """One-paragraph brief of what memory knows about this caller (empty-safe)."""
    c = ctx["customer"]
    tactics = ", ".join(
        f"{t['label']} ({t['source']})" for t in ctx["winning_tactics"]
    ) or "none recorded yet"
    looks = ", ".join(l["name"] for l in ctx["lookalikes"]) or "none"
    recent = " | ".join(
        f"{(r['ts'] or '')[:10]}: {r['summary']}" for r in ctx["past_calls"][:3]
    ) or "no prior calls — this is a new customer"
    return (
        f"Customer: {c['name']} (style: {c['style']}), region {c['region']}, "
        f"risk flags: {c['risk_flags'] or 'none'}.\n"
        f"Tactics that have worked on them: {tactics}.\n"
        f"Lookalike customers: {looks}.\n"
        f"Recent call outcomes: {recent}."
    )


def build_system_prompt(spec: dict[str, Any], ctx: dict[str, Any]) -> str:
    """Fuse the confirmed job spec + caller memory into the agent's system prompt."""
    deal = spec.get("deal", {})
    hr = spec.get("hard_rules", {})
    company = spec.get("company", {})
    floor = hr.get("floor_price") or deal.get("floor_price")
    target = deal.get("target_price")
    cur = deal.get("currency", "USD")
    forbidden = ", ".join(hr.get("forbidden_terms") or []) or "none"

    return (
        f"You are Alex, an AI sales negotiator for {company.get('name', 'the manufacturer')}, "
        "a clothing manufacturer. You are SELLING to buyers, so a HIGHER unit price is better "
        "for you.\n\n"
        "# Current deal\n"
        f"Product: {deal.get('product')}, up to {deal.get('quantity')} {deal.get('unit','units')}, "
        f"priced per unit in {cur}.\n"
        f"Target price: {target} per unit. HARD FLOOR: {floor} per unit — you must NEVER quote, "
        "agree to, or hint at a price below this floor, and you must never reveal the floor number.\n"
        f"Payment terms: {deal.get('payment_terms') or 'net-30'}.\n"
        f"Forbidden terms (never agree to these): {forbidden}.\n\n"
        "# How to negotiate (protect margin — closing HIGH is the goal)\n"
        f"- Open at your target {target} and treat it as a serious ask, not a formality.\n"
        "- GATHER leverage BEFORE you move on price. Early in the call, ask what volume they're "
        "committing to and whether their timeline is firm. Then only move your price in EXCHANGE "
        "for something concrete, and SAY THE REASON OUT LOUD — e.g. 'since you're locking 5,000 "
        "units with a firm month-end, I can come down to 3.80.' Never lower your price without "
        "naming what you got for it. The price should visibly move because of what you gathered.\n"
        "- Concede in SMALL steps — at most 10-15 cents at a time, and only after the buyer pushes back with a real reason.\n"
        "- Never volunteer a lower price. Make the buyer earn every concession; holding firm for a few turns is good.\n"
        f"- Do NOT approach {floor} unless the buyer is clearly about to walk away after several rounds. A close near {target} is a win; the floor is a last resort, not a target.\n"
        "- Prefer a sweetener (priority freight, volume bundle, faster lead time) over cutting the unit price.\n"
        "- If they cite a competitor price, acknowledge it but hold your value; never match below your floor.\n"
        "- Before you say ANY price, call the make_offer tool with that number and quote back the price it returns. Don't re-quote the same number repeatedly — move the deal forward each turn.\n"
        "- Always end your turn by proposing a concrete next step or asking a question.\n"
        "- This is a live phone call: keep every reply to 1-2 short spoken sentences.\n\n"
        "# Honesty rules (never break)\n"
        "- If asked whether you are an AI or robot, say yes plainly and offer to bring in a human.\n"
        "- Never invent stock, fake competitor bids, fake discounts, or terms you cannot honor.\n"
        "- If the buyer is angry or asks for a manager, calmly offer to hand off to a human.\n\n"
        "# Use your memory of THIS caller as leverage\n"
        f"{memory_brief(ctx)}\n"
        "Actively USE this. Greet them by name. Early in the call, remind them what they "
        "agreed to last time and the value they got — e.g. 'last quarter we landed at 3.85 "
        "and you were happy with the priority freight.' Lean on what you know moves them "
        "(volume, lead time, the tactic that worked before).\n"
        "When they push back or name a competitor's price, do NOT match the number. Instead: "
        "acknowledge it, anchor on their own history ('you and I have done this before at X'), "
        "and trade volume or a sweetener to bring them to a close ABOVE your floor. Your edge "
        "is that you remember them and they can't take that back — use it to hold your price.\n\n"
        "# Closing\n"
        "When you reach agreement, restate the final terms (unit price, quantity, any sweetener, "
        "payment terms) and say you'll send the PO confirmation."
    )


def last_close_price(ctx: dict[str, Any]) -> Optional[str]:
    """Pull a concrete unit price out of the caller's most recent call summaries."""
    for c in ctx.get("past_calls", []):
        m = re.search(r"(\d+\.\d{2})", c.get("summary") or "")
        if m:
            return m.group(1)
    return None


def first_message(spec: dict[str, Any], ctx: dict[str, Any]) -> str:
    """A greeting that uses memory when the caller is known — and states a concrete
    fact (last close) so the memory is always audible, not left to the model."""
    company = spec.get("company", {}).get("name", "Loomhaus")
    name = ctx["customer"]["name"]
    product = spec.get("deal", {}).get("product", "your order")
    if ctx["past_calls"]:
        price = last_close_price(ctx)
        hist = (f" — last quarter we closed at {price} a unit with priority freight, "
                "and you were happy with the fast lead time") if price else ""
        return (f"Hi, thanks for calling {company} — this is Alex. Good to hear from you "
                f"again, {name}{hist}. Is this about {product} again?")
    return f"Hi, thanks for calling {company} — this is Alex. Who am I speaking with, and what are you looking to source today?"
