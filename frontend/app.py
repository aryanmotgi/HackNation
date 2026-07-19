"""Manufacturer dashboard — Flask server (own localhost, separate from the arena CLI).

Reads the memory layer via get_context() and runs the negotiation arena (mock mode,
instant + deterministic) to produce live turn-by-turn threads. Both views —
dashboard and messaging — read one shared session cache so numbers stay consistent.

Run:
    .venv/bin/python -m frontend.app          # http://127.0.0.1:5001
"""

from __future__ import annotations

import os
from datetime import datetime

from flask import Flask, jsonify, render_template, request

from negotiation.arena import run_session
from negotiation.llm import MODEL, using_live_model
from intake.pdf_parse import parse_price_sheet
from intake.questions import questions_for, apply_answers
from intake.job_spec import build_job_spec, validate_spec, save_job_spec

# Shown on the dashboard in this order; Delta is the hidden lookalike made visible.
CUSTOMER_IDS = ["cust_alpha", "cust_bravo", "cust_charlie", "cust_delta"]

app = Flask(__name__)

_cache: dict | None = None  # last built snapshot


def _status(result: str) -> str:
    return {"closed": "won", "escalated": "needs-human", "no_deal": "active"}.get(result, "active")


def _build_snapshot() -> dict:
    """Reseed memory, run every customer's negotiation, compute metrics. Cached."""
    from memory.seed import seed
    seed()  # deterministic clean state for the demo

    sessions = []
    for cid in CUSTOMER_IDS:
        r = run_session(cid, quiet=True)
        r["status"] = _status(r["result"])
        sessions.append(r)

    closed = [s for s in sessions if s["result"] == "closed"]
    metrics = {
        "active_negotiations": sum(1 for s in sessions if s["status"] != "needs-human"),
        "deals_won": len(closed),
        "avg_price_capture": round(sum(s["price_capture"] for s in closed) / len(closed), 2)
        if closed else 0.0,
        "needs_human": sum(1 for s in sessions if s["status"] == "needs-human"),
        "total": len(sessions),
    }
    return {
        "model_mode": "live" if using_live_model() else "mock",
        "model": MODEL,
        "customers": sessions,
        "metrics": metrics,
    }


def _snapshot(force: bool = False) -> dict:
    global _cache
    if _cache is None or force:
        _cache = _build_snapshot()
    return _cache


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/messaging")
def messaging():
    return render_template("messaging.html")


@app.route("/graph")
def graph():
    return render_template("graph.html")


@app.route("/api/sessions")
def api_sessions():
    return jsonify(_snapshot())


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    return jsonify(_snapshot(force=True))


@app.route("/api/graph")
def api_graph():
    from memory.graph import get_full_graph
    _snapshot()  # ensure memory is seeded before reading the graph
    return jsonify(get_full_graph())


# ── Intake wizard ────────────────────────────────────────────────────────────

@app.route("/intake")
def intake():
    return render_template("intake.html")


@app.route("/api/intake/parse", methods=["POST"])
def api_intake_parse():
    """Step 2: parse an uploaded price-sheet PDF into a draft + the questions to ask."""
    f = request.files.get("pdf")
    if f is None:
        return jsonify({"error": "No PDF uploaded (field 'pdf')."}), 400
    try:
        draft = parse_price_sheet(f.read())
    except Exception as e:
        return jsonify({"error": f"Could not parse PDF: {e}"}), 400
    return jsonify({"draft": draft, "questions": questions_for(draft)})


@app.route("/api/intake/confirm", methods=["POST"])
def api_intake_confirm():
    """Step 4/5: build + validate the spec. Save only if valid AND confirm=True.

    Body: {draft, answers, confirm: bool}. When confirm is false this is a preview —
    returns the assembled spec + validation errors without saving. When confirm is
    true and there are no errors, saves a status='confirmed' job spec to jobs/.
    """
    body = request.get_json(force=True) or {}
    draft = body.get("draft", {})
    answers = body.get("answers", {})
    confirm = bool(body.get("confirm", False))

    # Merge any edited deal fields from the confirm screen over the parsed draft.
    edited = body.get("deal_edits") or {}
    merged_draft = {**draft, **{k: v for k, v in edited.items() if v not in (None, "")}}

    deal, hard_rules, audit = apply_answers(merged_draft, answers)
    spec = build_job_spec(
        deal=deal, hard_rules=hard_rules, questions=audit, source=body.get("source", "pdf"),
        created_at=datetime.now().isoformat(timespec="seconds"),
        status="confirmed" if confirm else "draft",
    )
    errors = validate_spec(spec)
    if errors:
        return jsonify({"ok": False, "errors": errors, "spec": spec}), 422
    if not confirm:
        return jsonify({"ok": True, "errors": [], "spec": spec})  # preview only
    path = save_job_spec(spec)
    return jsonify({"ok": True, "errors": [], "spec": spec,
                    "job_id": spec["job_id"], "path": os.path.relpath(path)})


# ── Voice intake — STUBBED (ElevenLabs wired later) ──────────────────────────

@app.route("/api/intake/voice/start", methods=["POST"])
@app.route("/api/intake/voice/answer", methods=["POST"])
def api_intake_voice_stub():
    """Placeholder for voice input + voice-answering the hard-rule questions.

    Both the 'Voice interview' input and voice answers to the Step-3 questions will
    run through ElevenLabs here. Not implemented yet.
    """
    return jsonify({"error": "Voice intake (ElevenLabs) coming soon."}), 501


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    print(f"Manufacturer dashboard → http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=True)
