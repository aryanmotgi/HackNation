"""Voice webhook service — the three seams that connect ElevenLabs to the brain.

Run standalone (own port, own single Kuzu connection; frontend app is untouched):
    .venv/bin/python -m voice.app          # serves on :5055

Expose publicly for ElevenLabs/Twilio with a tunnel, e.g.:
    cloudflared tunnel --url http://localhost:5055

Endpoints:
    GET  /health              liveness
    POST /call/init           conversation-initiation webhook
    POST /tool/make_offer      server tool — floor/guardrail enforced in code
    POST /call/postcall        post-call webhook — persist Call + Quote
    GET  /report               ranked quotes across all live calls (+recommendation)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from flask import Blueprint, Flask, jsonify, request

from memory.retrieve import (
    _conn, create_customer, find_customer_by_phone, get_context,
    write_call, write_quote,
)
from negotiation.scoring import price_capture, score_session
from .spec import build_system_prompt, first_message, load_active_spec

load_dotenv()

# Exposed as a Blueprint so it can share ONE Flask process (and one Kuzu
# connection) with the frontend — see serve.py. Still runnable standalone below.
voice_bp = Blueprint("voice", __name__)

MAX_TURNS = 12
RAW_LOG = "/tmp/voice_payloads.log"

# --- demo caller state (works around web-widget lacking phone/dynamic-var round-trip) ---
# The dashboard test widget may not fire the init webhook or round-trip our dynamic
# variables. So we let the demo PIN who the next caller is (POST /demo/set_caller),
# and remember the last resolved caller so /call/postcall attributes the quote
# correctly even when dynamic_variables don't come back.
_PINNED_CALLER: Optional[str] = None
_LAST_CALLER: Optional[str] = None
_ANON_SEQ = 0


def _raw_log(tag: str, body: dict) -> None:
    """Append a raw webhook payload for diagnosis (best-effort)."""
    try:
        with open(RAW_LOG, "a") as f:
            f.write(f"\n=== {tag} ===\n{json.dumps(body)[:4000]}\n")
    except OSError:
        pass


# --- helpers -----------------------------------------------------------------

def _ensure_live_deal(spec: dict[str, Any], customer_id: str) -> str:
    """Upsert a Deal node from the active spec and link the caller to it.

    Keeps the graph/dashboard coherent for live callers. Returns the deal id.
    """
    deal = spec.get("deal", {})
    deal_id = f"deal_{spec.get('job_id', 'live')}"
    conn = _conn()
    if not _rows_exist(conn, "MATCH (d:Deal {id:$id}) RETURN d.id", {"id": deal_id}):
        conn.execute(
            "CREATE (:Deal {id:$id, product:$product, floor_price:$floor, "
            "target_price:$target, currency:$cur, status:'open'})",
            {"id": deal_id, "product": deal.get("product"),
             "floor": float(deal.get("floor_price") or 0),
             "target": float(deal.get("target_price") or 0),
             "cur": deal.get("currency", "USD")},
        )
    if not _rows_exist(conn,
                       "MATCH (:Customer {id:$c})-[:HAS_DEAL]->(:Deal {id:$d}) RETURN 1",
                       {"c": customer_id, "d": deal_id}):
        conn.execute(
            "MATCH (c:Customer {id:$c}), (d:Deal {id:$d}) CREATE (c)-[:HAS_DEAL]->(d)",
            {"c": customer_id, "d": deal_id},
        )
    return deal_id


def _rows_exist(conn, cypher: str, params: dict) -> bool:
    r = conn.execute(cypher, params)
    return r.has_next()


def _num(v: Any) -> Optional[float]:
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def _dc_value(dc: dict, key: str) -> Any:
    """Pull a value out of ElevenLabs data_collection_results (nested {value:..})."""
    v = (dc or {}).get(key)
    return v.get("value") if isinstance(v, dict) else v


def _elevenlabs_signed_url(agent_id: str, key: str) -> Optional[str]:
    """Fetch a signed WebSocket URL so the browser SDK can start an authenticated
    conversation without exposing the API key client-side."""
    import ssl
    import urllib.request
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    url = ("https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"
           f"?agent_id={agent_id}")
    req = urllib.request.Request(url, headers={"xi-api-key": key})
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        return json.load(r).get("signed_url")


@voice_bp.route("/health", methods=["GET"])
def health():
    spec = load_active_spec()
    return jsonify({"ok": True, "active_job": spec.get("job_id"),
                    "floor": spec.get("deal", {}).get("floor_price")})


# --- seam A: conversation-initiation webhook ---------------------------------

@voice_bp.route("/demo/set_caller", methods=["POST"])
def set_caller():
    """Pin who the NEXT call is from (e.g. cust_alpha) — for scripted demos where
    the web widget carries no phone number. Consumed by the next /call/init."""
    global _PINNED_CALLER
    body = request.get_json(force=True, silent=True) or {}
    _PINNED_CALLER = body.get("customer_id") or None
    return jsonify({"ok": True, "pinned_caller": _PINNED_CALLER})


@voice_bp.route("/call/init", methods=["POST"])
def call_init():
    """Identify the caller, load spec+memory, return the per-call prompt."""
    global _PINNED_CALLER, _LAST_CALLER, _ANON_SEQ
    body = request.get_json(force=True, silent=True) or {}
    _raw_log("call/init", body)
    caller = (body.get("caller_id") or body.get("from")
              or (body.get("call") or {}).get("from") or "")

    if _PINNED_CALLER:                         # scripted demo: use the pinned caller
        customer_id, _PINNED_CALLER = _PINNED_CALLER, None
    elif caller:                               # real phone call: identify by number
        customer_id = find_customer_by_phone(caller) or create_customer(caller)
    else:                                      # web widget, no phone: unique caller
        _ANON_SEQ += 1
        customer_id = create_customer(f"+1999000{_ANON_SEQ:04d}", name=f"Web Caller {_ANON_SEQ}")
    _LAST_CALLER = customer_id

    spec = load_active_spec()
    ctx = get_context(customer_id)
    deal_id = _ensure_live_deal(spec, customer_id)
    deal = spec.get("deal", {})

    dynamic_vars = {
        "customer_id": customer_id,
        "customer_name": ctx["customer"]["name"],
        "deal_id": deal_id,
        "product": deal.get("product"),
        "floor_price": deal.get("floor_price"),
        "target_price": deal.get("target_price"),
        "currency": deal.get("currency", "USD"),
    }
    return jsonify({
        "type": "conversation_initiation_client_data",
        "dynamic_variables": dynamic_vars,
        "conversation_config_override": {
            "agent": {
                "prompt": {"prompt": build_system_prompt(spec, ctx)},
                "first_message": first_message(spec, ctx),
            }
        },
    })


# --- dashboard call control: mint a signed URL + per-caller overrides --------

@voice_bp.route("/call/token", methods=["GET"])
def call_token():
    """Start a REAL browser call from the dashboard for a chosen customer.

    Returns a signed URL (so the API key stays server-side) plus the overrides
    the browser SDK should pass: the customer's memory + confirmed spec injected
    as a prompt override. This is why the SDK path fixes personalization — unlike
    the test widget, client-side overrides ARE applied, so the confirmed spec is
    reused verbatim on every call.
    """
    global _LAST_CALLER
    customer_id = request.args.get("customer_id") or _PINNED_CALLER or "cust_alpha"
    key = os.getenv("ELEVENLABS_API_KEY")
    agent_id = os.getenv("ELEVENLABS_AGENT_ID", "")
    if not key or not agent_id:
        return jsonify({"error": "ELEVENLABS_API_KEY / ELEVENLABS_AGENT_ID not set"}), 500

    spec = load_active_spec()
    try:
        ctx = get_context(customer_id)
    except KeyError:
        customer_id = create_customer("+10000000000", name="Web Caller")
        ctx = get_context(customer_id)
    _ensure_live_deal(spec, customer_id)
    _LAST_CALLER = customer_id  # so /call/postcall attributes the quote correctly
    deal = spec.get("deal", {})

    try:
        signed = _elevenlabs_signed_url(agent_id, key)
    except Exception as e:  # noqa: BLE001 — surface the error to the caller
        return jsonify({"error": f"signed-url fetch failed: {type(e).__name__}"}), 502

    return jsonify({
        "signed_url": signed,
        "agent_id": agent_id,
        "customer_id": customer_id,
        "customer_name": ctx["customer"]["name"],
        "overrides": {
            "agent": {
                "prompt": {"prompt": build_system_prompt(spec, ctx)},
                "first_message": first_message(spec, ctx),
            }
        },
        "dynamic_variables": {
            "customer_id": customer_id,
            "customer_name": ctx["customer"]["name"],
            "product": deal.get("product"),
            "floor_price": deal.get("floor_price"),
            "target_price": deal.get("target_price"),
        },
    })


# --- seam B: make_offer server tool (floor enforced in code) -----------------

@voice_bp.route("/tool/make_offer", methods=["POST"])
def make_offer():
    """Validate a proposed price against the floor + hard rules. Clamp if needed."""
    body = request.get_json(force=True, silent=True) or {}
    params = body.get("parameters") or body
    offer = _num(params.get("offer_price") or params.get("price"))
    quantity = _num(params.get("quantity"))

    spec = load_active_spec()
    hr = spec.get("hard_rules", {})
    deal = spec.get("deal", {})
    floor = _num(hr.get("floor_price") or deal.get("floor_price")) or 0.0
    cur = deal.get("currency", "USD")

    if offer is None:
        return jsonify({"approved": False, "reason": "no offer_price provided"}), 200

    notes = []
    approved = offer
    if offer < floor:
        approved = floor
        notes.append(f"Requested {offer} is below the floor; clamped to {floor}.")
        say = f"The best I can responsibly do is {floor} {cur} per unit."
    else:
        say = f"I can do {approved} {cur} per unit."

    # Large-order escalation (transfer_deals_above on total value).
    transfer_above = _num(hr.get("transfer_deals_above"))
    escalate = bool(transfer_above and quantity and approved * quantity > transfer_above)
    if escalate:
        notes.append("Order value exceeds the auto-transfer threshold — offer to bring in a human.")

    return jsonify({
        "approved": True,
        "approved_price": round(approved, 2),
        "currency": cur,
        "say": say + " What volume are you locking in so I can firm this up?",
        "escalate_to_human": escalate,
        "notes": notes,
    })


# --- seam C: post-call webhook -----------------------------------------------

@voice_bp.route("/call/postcall", methods=["POST"])
def post_call():
    """Persist the call + an itemized quote from ElevenLabs' extracted data."""
    body = request.get_json(force=True, silent=True) or {}
    _raw_log("call/postcall", body)
    data = body.get("data") or body
    conv_id = data.get("conversation_id") or "unknown"

    init = (data.get("conversation_initiation_client_data") or {})
    dv = init.get("dynamic_variables") or {}
    analysis = data.get("analysis") or {}
    dc = analysis.get("data_collection_results") or {}
    transcript_turns = data.get("transcript") or []

    # Who was this? Prefer the customer_id injected at call start; then the phone;
    # then the last caller; then the pinned caller (the web widget never fires
    # /call/init, so the pin is the only reliable signal for a scripted demo).
    global _PINNED_CALLER
    customer_id = dv.get("customer_id")
    if not customer_id:
        phone = (((data.get("metadata") or {}).get("phone_call") or {}).get("external_number"))
        customer_id = (find_customer_by_phone(phone) if phone else None) or _LAST_CALLER
    if not customer_id and _PINNED_CALLER:
        customer_id, _PINNED_CALLER = _PINNED_CALLER, None
    if not customer_id:
        customer_id = create_customer("+10000000000")

    spec = load_active_spec()
    deal = spec.get("deal", {})
    floor = _num(deal.get("floor_price")) or 0.0
    target = _num(deal.get("target_price")) or floor
    deal_id = dv.get("deal_id") or _ensure_live_deal(spec, customer_id)

    outcome = (_dc_value(dc, "outcome") or "declined").lower()
    agreed_price = _num(_dc_value(dc, "agreed_price"))
    quantity = _num(_dc_value(dc, "quantity")) or _num(deal.get("quantity"))
    sweetener = _dc_value(dc, "sweetener")
    competitor = _num(_dc_value(dc, "competitor_price"))

    closed = outcome == "closed" and agreed_price is not None
    turns = max(2, len([t for t in transcript_turns if (t.get("role") == "agent")]))
    scored = score_session(
        floor=floor, target=target, closed=closed, escalated=(outcome == "callback"),
        agreed_price=agreed_price, best_offer=agreed_price or competitor,
        turns=turns, max_turns=MAX_TURNS,
    )

    ts = _timestamp(data)
    summary = _build_summary(outcome, agreed_price, quantity, sweetener, competitor,
                             deal.get("currency", "USD"), analysis)
    recording_url = f"https://api.elevenlabs.io/v1/convai/conversations/{conv_id}/audio"
    transcript_text = _flatten_transcript(transcript_turns)

    call_id = write_call(
        customer_id, deal_id, summary, scored["sentiment"], scored["outcome_score"], ts,
        recording_url=recording_url, transcript=transcript_text,
    )
    quote_id = write_quote(
        call_id, customer_id, product=deal.get("product", "unknown"),
        unit_price=agreed_price, quantity=int(quantity) if quantity else None,
        currency=deal.get("currency", "USD"),
        fees=[sweetener] if sweetener else [], terms=deal.get("payment_terms"),
        sweetener=sweetener, outcome=outcome, ts=ts,
    )
    return jsonify({"ok": True, "call_id": call_id, "quote_id": quote_id,
                    "outcome": outcome, "score": scored["outcome_score"]})


# --- ranked report -----------------------------------------------------------

@voice_bp.route("/report", methods=["GET"])
def report():
    """Rank every live-call quote by manufacturer value; cite recordings."""
    conn = _conn()
    spec = load_active_spec()
    floor = _num(spec.get("deal", {}).get("floor_price")) or 0.0
    target = _num(spec.get("deal", {}).get("target_price")) or floor

    rows = []
    r = conn.execute(
        "MATCH (k:Call)-[:PRODUCED]->(q:Quote) "
        "RETURN q.customer_id, q.product, q.unit_price, q.quantity, q.currency, "
        "q.sweetener, q.outcome, q.total, k.recording_url, k.ts ORDER BY q.ts DESC"
    )
    while r.has_next():
        (cust, product, unit, qty, cur, sweet, outcome, total, rec, ts) = r.get_next()
        capture = price_capture(unit, floor, target) if unit is not None else 0.0
        rows.append({
            "customer_id": cust, "product": product, "unit_price": unit,
            "quantity": qty, "currency": cur, "sweetener": sweet, "outcome": outcome,
            "total": total, "price_capture": round(capture, 2),
            "recording_url": rec, "ts": ts,
        })
    # Rank: closed first, then higher price_capture, then higher total.
    rows.sort(key=lambda x: (x["outcome"] == "closed", x["price_capture"], x["total"] or 0),
              reverse=True)
    recommendation = _plain_recommendation(rows, spec)
    return jsonify({"floor": floor, "target": target, "ranked_quotes": rows,
                    "recommendation": recommendation})


# --- small deterministic text helpers ----------------------------------------

def _timestamp(data: dict) -> str:
    md = data.get("metadata") or {}
    for key in ("start_time_unix_secs", "accepted_time_unix_secs", "call_start_time_unix_secs"):
        v = md.get(key)
        if isinstance(v, (int, float)) and v > 0:
            return datetime.fromtimestamp(v, tz=timezone.utc).replace(tzinfo=None).isoformat()
    return str(md.get("start_time") or md.get("call_start_time") or "2026-07-18T00:00:00")


def _flatten_transcript(turns: list) -> str:
    out = []
    for t in turns:
        msg = (t.get("message") or "").strip()
        if msg:
            out.append(f"{t.get('role', '?')}: {msg}")
    return "\n".join(out)[:8000]


def _build_summary(outcome, price, qty, sweetener, competitor, cur, analysis) -> str:
    s = analysis.get("transcript_summary")
    if s:
        return str(s)[:600]
    if outcome == "closed" and price is not None:
        extra = f" with {sweetener}" if sweetener else ""
        return f"Closed at {price} {cur}/unit on {qty or '?'} units{extra}."
    if outcome == "callback":
        return "Buyer wants a callback / time to think; no price agreed."
    comp = f" Buyer cited a competitor at {competitor}." if competitor else ""
    return f"No deal reached.{comp}"


def _plain_recommendation(rows: list, spec: dict) -> str:
    closed = [r for r in rows if r["outcome"] == "closed"]
    if not closed:
        return "No deals closed yet — no recommendation."
    best = closed[0]
    return (f"Recommend locking {best['customer_id']} at {best['unit_price']} "
            f"{best['currency']}/unit ({best['quantity']} units) — highest-value close, "
            f"price capture {best['price_capture']}. See the call recording for evidence.")


def create_app() -> Flask:
    """Standalone Flask app serving only the voice blueprint."""
    app = Flask(__name__)
    app.register_blueprint(voice_bp)
    return app


if __name__ == "__main__":
    port = int(os.getenv("VOICE_PORT", "5055"))
    print(f"[voice] webhook service on :{port} — /call/init /tool/make_offer /call/postcall /report")
    create_app().run(host="0.0.0.0", port=port)
