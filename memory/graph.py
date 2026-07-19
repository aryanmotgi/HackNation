"""Full-graph export for visualization — reads the existing Kuzu store, no new data.

get_full_graph() returns every node (Customer, Deal, Call, Pattern) with its full
properties and every relationship as edges, shaped for a node-link diagram:

    {
      "nodes": [{"id","type","label","meta":{...},"escalate":bool?}, ...],
      "edges": [{"source","target","type"}, ...],
    }

Call nodes carry their summary, sentiment, outcome_score and timestamp so the graph
view can show the actual seeded call data on click.
"""

from __future__ import annotations

from typing import Any

from .retrieve import _conn, _rows, _should_escalate


def get_full_graph() -> dict[str, Any]:
    conn = _conn()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # --- Manufacturer hub (root) — connects every customer into one component ---
    HUB = "mfr_root"
    nodes.append({
        "id": HUB, "type": "Manufacturer", "label": "Lowball",
        "meta": {"note": "The manufacturer. Every customer account hangs off this hub."},
    })

    # --- Customer nodes (with escalation flag from their call history) ---
    for r in _rows(conn.execute(
        "MATCH (c:Customer) RETURN c.id, c.name, c.region, c.negotiation_style, c.risk_flags"
    )):
        cid = r[0]
        edges.append({"source": HUB, "target": cid, "type": "ACCOUNT"})
        scores = [row[0] for row in _rows(conn.execute(
            "MATCH (c:Customer {id:$id})-[:HAD_CALL]->(k:Call) "
            "RETURN k.outcome_score ORDER BY k.ts DESC", {"id": cid}))]
        nodes.append({
            "id": cid, "type": "Customer", "label": r[1],
            "escalate": _should_escalate(scores),
            "meta": {"region": r[2], "style": r[3], "risk_flags": r[4] or [],
                     "recent_scores": scores},
        })

    # --- Deal nodes ---
    for r in _rows(conn.execute(
        "MATCH (d:Deal) RETURN d.id, d.product, d.floor_price, d.target_price, d.currency, d.status"
    )):
        nodes.append({
            "id": r[0], "type": "Deal", "label": r[1],
            "meta": {"floor_price": r[2], "target_price": r[3],
                     "currency": r[4], "status": r[5]},
        })

    # --- Call nodes (full seeded call data) ---
    for r in _rows(conn.execute(
        "MATCH (k:Call) RETURN k.id, k.ts, k.summary, k.sentiment, k.outcome_score ORDER BY k.ts"
    )):
        nodes.append({
            "id": r[0], "type": "Call", "label": r[1][:10],  # date as label
            "meta": {"ts": r[1], "summary": r[2], "sentiment": r[3], "outcome_score": r[4]},
        })

    # --- Pattern nodes ---
    for r in _rows(conn.execute(
        "MATCH (p:Pattern) RETURN p.id, p.label, p.detail"
    )):
        nodes.append({
            "id": r[0], "type": "Pattern", "label": r[1],
            "meta": {"detail": r[2]},
        })

    # --- Edges (one query per relationship type) ---
    rel_queries = [
        ("HAS_DEAL",   "MATCH (a:Customer)-[:HAS_DEAL]->(b:Deal) RETURN a.id, b.id"),
        ("HAD_CALL",   "MATCH (a:Customer)-[:HAD_CALL]->(b:Call) RETURN a.id, b.id"),
        ("ABOUT",      "MATCH (a:Call)-[:ABOUT]->(b:Deal) RETURN a.id, b.id"),
        ("EXHIBITS",   "MATCH (a:Customer)-[:EXHIBITS]->(b:Pattern) RETURN a.id, b.id"),
        ("WORKED",     "MATCH (a:Pattern)-[:WORKED]->(b:Customer) RETURN a.id, b.id"),
        ("SIMILAR_TO", "MATCH (a:Customer)-[:SIMILAR_TO]->(b:Customer) RETURN a.id, b.id"),
    ]
    for rel_type, q in rel_queries:
        for r in _rows(conn.execute(q)):
            edges.append({"source": r[0], "target": r[1], "type": rel_type})

    return {"nodes": nodes, "edges": edges}
