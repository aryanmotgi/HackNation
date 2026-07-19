"""Retrieval + write-back — the public contract the agent codes against.

    get_context(customer_id)  -> dict  assemble everything the agent needs pre-call
    write_call(...)           -> str   persist a post-call summary + outcome
    search_patterns(text, k)  -> list  semantic tactic lookup (RAG, vector index)

get_context intentionally sources tactics/lookalikes from GRAPH EDGES (not live
vector search) so its output is deterministic and demo-safe. The vector index
powers search_patterns only.
"""

from __future__ import annotations

from typing import Any, Optional

import kuzu

from .embeddings import embed
from .schema import DEFAULT_DB_PATH, PATTERN_INDEX, connect

# Recent calls to surface, and how many trailing calls the escalation rule scans.
RECENT_CALLS = 5
ESCALATION_WINDOW = 3
ESCALATION_FLOOR = 0.25  # a single latest score below this also escalates

_CONN: Optional[kuzu.Connection] = None
_DB = None
_DB_PATH = DEFAULT_DB_PATH


def _conn() -> kuzu.Connection:
    """Lazily open and cache the module-level connection."""
    global _CONN, _DB
    if _CONN is None:
        _DB, _CONN = connect(_DB_PATH)
    return _CONN


def use_database(db_path: str) -> None:
    """Point the module at a different db path (tests). Resets the connection."""
    global _CONN, _DB, _DB_PATH
    _CONN, _DB, _DB_PATH = None, None, db_path


def _rows(result: kuzu.QueryResult) -> list[list[Any]]:
    out = []
    while result.has_next():
        out.append(result.get_next())
    return out


# --- Escalation --------------------------------------------------------------

def _should_escalate(scores_newest_first: list[float]) -> bool:
    """Flag human handoff when recent outcomes are trending down.

    Escalate if the last ESCALATION_WINDOW calls are strictly declining
    (oldest -> newest), or the single latest score is below ESCALATION_FLOOR.
    """
    if not scores_newest_first:
        return False
    if scores_newest_first[0] < ESCALATION_FLOOR:
        return True
    window = scores_newest_first[:ESCALATION_WINDOW]
    if len(window) < ESCALATION_WINDOW:
        return False
    oldest_first = list(reversed(window))
    return all(a > b for a, b in zip(oldest_first, oldest_first[1:]))


# --- Read --------------------------------------------------------------------

def get_context(customer_id: str) -> dict[str, Any]:
    """Assemble the agent's pre-call context for one customer.

    Returns:
        {
          customer: {id, name, region, style, risk_flags},
          open_deal: {id, product, floor_price, target_price, currency, status} | None,
          past_calls: [{id, ts, summary, sentiment, outcome_score}, ...],  # newest first
          winning_tactics: [{pattern_id, label, description, weight, source}, ...],
          lookalikes: [{id, name, style, weight}, ...],
          escalate: bool,
        }
    Raises KeyError if the customer does not exist.
    """
    conn = _conn()

    cust = _rows(conn.execute(
        "MATCH (c:Customer {id:$id}) "
        "RETURN c.id, c.name, c.region, c.negotiation_style, c.risk_flags",
        {"id": customer_id},
    ))
    if not cust:
        raise KeyError(f"Unknown customer: {customer_id}")
    cid, name, region, style, flags = cust[0]
    customer = {"id": cid, "name": name, "region": region,
                "style": style, "risk_flags": flags or []}

    deal_rows = _rows(conn.execute(
        "MATCH (c:Customer {id:$id})-[:HAS_DEAL]->(d:Deal) WHERE d.status = 'open' "
        "RETURN d.id, d.product, d.floor_price, d.target_price, d.currency, d.status "
        "LIMIT 1",
        {"id": customer_id},
    ))
    open_deal = None
    if deal_rows:
        d = deal_rows[0]
        open_deal = {"id": d[0], "product": d[1], "floor_price": d[2],
                     "target_price": d[3], "currency": d[4], "status": d[5]}

    call_rows = _rows(conn.execute(
        "MATCH (c:Customer {id:$id})-[:HAD_CALL]->(k:Call) "
        "RETURN k.id, k.ts, k.summary, k.sentiment, k.outcome_score "
        "ORDER BY k.ts DESC LIMIT $n",
        {"id": customer_id, "n": RECENT_CALLS},
    ))
    past_calls = [
        {"id": r[0], "ts": r[1], "summary": r[2],
         "sentiment": r[3], "outcome_score": r[4]}
        for r in call_rows
    ]

    # Winning tactics: patterns that worked on this customer directly...
    own = _rows(conn.execute(
        "MATCH (p:Pattern)-[w:WORKED]->(c:Customer {id:$id}) "
        "RETURN p.id, p.label, p.detail, w.weight",
        {"id": customer_id},
    ))
    # ...plus tactics that worked on lookalike customers (tactic transfer).
    via_similar = _rows(conn.execute(
        "MATCH (c:Customer {id:$id})-[:SIMILAR_TO]->(o:Customer)<-[w:WORKED]-(p:Pattern) "
        "RETURN p.id, p.label, p.detail, w.weight",
        {"id": customer_id},
    ))
    tactics: dict[str, dict[str, Any]] = {}
    for pid, label, desc, weight in own:
        tactics[pid] = {"pattern_id": pid, "label": label, "description": desc,
                        "weight": weight, "source": "self"}
    for pid, label, desc, weight in via_similar:
        if pid not in tactics:  # prefer a direct 'self' hit over a lookalike one
            tactics[pid] = {"pattern_id": pid, "label": label, "description": desc,
                            "weight": weight, "source": "lookalike"}
    winning_tactics = sorted(tactics.values(), key=lambda t: t["weight"], reverse=True)

    look_rows = _rows(conn.execute(
        "MATCH (c:Customer {id:$id})-[s:SIMILAR_TO]->(o:Customer) "
        "RETURN o.id, o.name, o.negotiation_style, s.weight ORDER BY s.weight DESC",
        {"id": customer_id},
    ))
    lookalikes = [{"id": r[0], "name": r[1], "style": r[2], "weight": r[3]}
                  for r in look_rows]

    escalate = _should_escalate([c["outcome_score"] for c in past_calls])

    return {
        "customer": customer,
        "open_deal": open_deal,
        "past_calls": past_calls,
        "winning_tactics": winning_tactics,
        "lookalikes": lookalikes,
        "escalate": escalate,
    }


def search_patterns(query_text: str, k: int = 3) -> list[dict[str, Any]]:
    """Semantic tactic lookup via the HNSW vector index (RAG during a call)."""
    conn = _conn()
    from .embeddings import EMBED_DIM
    # QUERY_VECTOR_INDEX requires a literal/typed vector, not CAST($param), so the
    # float list is inlined. Values come from embed() (numbers only) — no injection.
    vec_literal = "[" + ",".join(repr(float(x)) for x in embed(query_text)) + "]"
    result = conn.execute(
        f"CALL QUERY_VECTOR_INDEX('Pattern', '{PATTERN_INDEX}', "
        f"CAST({vec_literal} AS FLOAT[{EMBED_DIM}]), $k) "
        "RETURN node.id, node.label, node.detail, distance ORDER BY distance",
        {"k": k},
    )
    return [{"pattern_id": r[0], "label": r[1], "description": r[2], "distance": r[3]}
            for r in _rows(result)]


# --- Write -------------------------------------------------------------------

def write_call(
    customer_id: str,
    deal_id: str,
    summary: str,
    sentiment: float,
    outcome_score: float,
    ts: str,
) -> str:
    """Persist a post-call record (summary, not raw transcript) and its edges.

    Stores an embedding of the summary for future Call-level search. The new call
    is immediately visible to get_context (graph query). It is NOT added to the
    live vector index — persisted HNSW indexes don't rebuild cleanly on reopen, so
    Call vector search reflects the last seed build. Re-seed to refresh it.

    Returns the generated call id.
    """
    conn = _conn()
    call_id = f"call_{customer_id}_{ts}".replace(":", "").replace("-", "")
    conn.execute(
        "CREATE (:Call {id:$id, ts:$ts, summary:$summary, sentiment:$sent, "
        "outcome_score:$score, embedding:$emb})",
        {"id": call_id, "ts": ts, "summary": summary, "sent": sentiment,
         "score": outcome_score, "emb": embed(summary)},
    )
    conn.execute(
        "MATCH (c:Customer {id:$cid}), (k:Call {id:$kid}) CREATE (c)-[:HAD_CALL]->(k)",
        {"cid": customer_id, "kid": call_id},
    )
    conn.execute(
        "MATCH (k:Call {id:$kid}), (d:Deal {id:$did}) CREATE (k)-[:ABOUT]->(d)",
        {"kid": call_id, "did": deal_id},
    )
    return call_id
