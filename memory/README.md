# Memory Layer — the foundation

Kuzu graph + native HNSW vector index in **one embedded engine**. Graph traversal,
semantic search, and RAG all live here — no separate vector DB.

This is what every other subsystem builds on. Teammates code against `get_context`
and `write_call`; nobody else touches Kuzu directly.

## Setup

```bash
python3.12 -m venv .venv          # kuzu has no wheel for 3.14 yet — use 3.12
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m memory.seed   # build ./memory/data/kuzu_db with demo data
```

## The contract

```python
from memory.retrieve import get_context, write_call, search_patterns
```

### `get_context(customer_id) -> dict`
Everything the agent needs **before** a call. Deterministic (graph-sourced).

```python
{
  "customer":  {"id","name","region","style","risk_flags":[...]},
  "open_deal": {"id","product","floor_price","target_price","currency","status"} | None,
  "past_calls":[{"id","ts","summary","sentiment","outcome_score"}, ...],  # newest first, max 5
  "winning_tactics":[{"pattern_id","label","description","weight","source"}, ...],
        # source = "self" (worked on this customer) or "lookalike" (worked on a similar one)
  "lookalikes":[{"id","name","style","weight"}, ...],
  "escalate": bool,   # True -> hand to a human, don't run autonomously
}
```
Raises `KeyError` for an unknown customer.

### `write_call(customer_id, deal_id, summary, sentiment, outcome_score, ts) -> str`
Persist a post-call record **after** a call. Store a short `summary`, NOT the raw
transcript. Immediately visible to `get_context`. Returns the new call id.

### `search_patterns(query_text, k=3) -> list`
Semantic tactic lookup via the vector index (optional, RAG during a call).
Returns `[{"pattern_id","label","description","distance"}, ...]`.

## Escalation rule
`escalate=True` when the last 3 calls' `outcome_score` strictly decline, or the
latest score is below 0.25. Logic in `retrieve._should_escalate`.

## Guardrails (enforced by the agent, data lives here)
- Never quote below `open_deal.floor_price`.
- Always propose a next step.
- `risk_flags` and `escalate` gate autonomous behavior.

## ⚠️ Before the demo
`memory/embeddings.py` is a **stub** — deterministic but not semantic. `get_context`
(graph edges) is fully meaningful now; `search_patterns` (vectors) is noise until you
swap in a real model. `EMBED_DIM=384` already matches `all-MiniLM-L6-v2`, so the swap
needs **no schema change** — replace the body of `embed()`, then re-run `memory.seed`.

## Files
| file | purpose |
|------|---------|
| `schema.py` | Kuzu connection, node/rel tables, vector index build |
| `embeddings.py` | `embed(text)` — **stub, swap before demo** |
| `seed.py` | demo data (4 customers incl. a lookalike pair + a declining/escalating one) |
| `retrieve.py` | `get_context`, `write_call`, `search_patterns` — the public API |

## Graph model
```
(Customer)-[:HAS_DEAL]->(Deal)
(Customer)-[:HAD_CALL]->(Call)-[:ABOUT]->(Deal)
(Customer)-[:EXHIBITS]->(Pattern)        # behavior the customer shows
(Pattern)-[:WORKED {weight}]->(Customer) # tactic that produced a good outcome
(Customer)-[:SIMILAR_TO {weight}]->(Customer)  # lookalikes (precomputed)
```
Tactic transfer: a tactic that `WORKED` on a `SIMILAR_TO` customer surfaces in
`winning_tactics` with `source="lookalike"`.
