"""Manufacturer dashboard — Flask server (own localhost, separate from the arena CLI).

Reads the memory layer via get_context() and runs the negotiation arena (mock mode,
instant + deterministic) to produce live turn-by-turn threads. Both views —
dashboard and messaging — read one shared session cache so numbers stay consistent.

Run:
    .venv/bin/python -m frontend.app          # http://127.0.0.1:5001
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template

from negotiation.arena import run_session
from negotiation.llm import MODEL, using_live_model

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


@app.route("/api/sessions")
def api_sessions():
    return jsonify(_snapshot())


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    return jsonify(_snapshot(force=True))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    print(f"Manufacturer dashboard → http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=True)
