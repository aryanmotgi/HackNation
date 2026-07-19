# Loomhaus — memory-driven negotiation agent (manufacturer side)

**Foundation branch: memory layer + negotiation arena.** (Voice calling and the web
frontend are separate branches — see *Team split* at the bottom.)

A B2B negotiation AI for manufacturers. A manufacturer has thousands of customers who
each negotiate differently — some grind hard, some agree fast, some stall. The agent
negotiates with each one, **remembers every customer**, adapts its approach from that
memory, enforces guardrails in code, and **escalates to a human when deals go bad**.

The differentiator is **memory**: a Kuzu graph + native vector index in one engine.
This is **retrieval-augmented adaptation, not model training** — the agent adapts per
customer from memory; the model itself is never retrained.

## Architecture

```
   ┌─────────────────────────── memory/ (Kuzu graph + HNSW vectors) ───────────────────────────┐
   │  Customer · Deal · Call · Pattern   +   one embedded engine (graph + vector, no separate DB) │
   └───────────────▲───────────────────────────────────────────────────────────────▲────────────┘
                   │ write_call(summary, score, sentiment)          get_context(customer) │
                   │  (learning loop — memory grows)          (style, floor, tactics,      │
                   │                                           lookalikes, escalate flag)  │
   ┌───────────────┴───────────────────────────────────────────────────────────────┴────────────┐
   │                                negotiation/  —  the agent                                     │
   │   get_context() ─► build prompt from memory ─► negotiate turn-by-turn ─► score ─► write_call() │
   │                              (guardrails enforced in CODE)                                     │
   └───────────────▲───────────────────────────────────────────────────────────────┬────────────┘
                   │ customer reply                                    agent offer + reasoning │
                   └───────────────────────── customer_bot (LLM persona) ◄──────────────────────┘
```

The loop closes: each session writes a summary + score back to memory, so a run of
declining scores is exactly what the next `get_context()` flags for human handoff.

## Setup

```bash
python3.12 -m venv .venv           # kuzu has no wheel for 3.14 yet — use 3.12
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m memory.seed    # build the graph with demo data
```

Optional — go live (otherwise a deterministic offline mock runs):
```bash
cp .env.example .env               # add OPENAI_API_KEY (model: gpt-5.6-terra)
```

## Run

```bash
.venv/bin/python -m negotiation.demo   # watch the agent negotiate all 3 styles
.venv/bin/python -m tests.smoke        # 25-check end-to-end verification (offline)
```

## The demo

Same product for everyone — Cotton T-shirts, floor 3.20 / target 4.00 USD. Only the
customer changes, so outcomes come purely from adaptation:

| customer | style | agent behavior | outcome |
|----------|-------|----------------|---------|
| Alpha Textiles | hard haggler | anchors high, grinds, holds above floor | closes 3.68 |
| Bravo Imports | responsive | rapport, closes fast near target | closes 4.16 |
| Charlie Retail | staller | sees declining history → **escalates to human** | handed off |
| Delta Fashion | lookalike | wins using a tactic **transferred from Alpha** | closes 3.68 |

## Public interface (what other branches build on — DO NOT change these signatures)

```python
from memory.retrieve import get_context, write_call, search_patterns
# get_context(customer_id)   -> dict  (customer, open_deal, past_calls, winning_tactics, lookalikes, escalate)
# write_call(customer_id, deal_id, summary, sentiment, outcome_score, ts) -> str
# search_patterns(text, k=3) -> list
```

## Before the demo
- **Swap the embedder** — `memory/embeddings.py` is a stub. `get_context` (graph) is
  fully real; `search_patterns` (vectors) is noise until `all-MiniLM-L6-v2` is dropped
  in. `EMBED_DIM=384` already matches it → no schema change.
- **Add `OPENAI_API_KEY`** to make reasoning model-generated (mock proves the logic).

## Status
- ✅ memory layer, negotiation arena, guardrails, escalation, scoring
- ✅ 25-check smoke test passing on the offline mock
- ⏳ live OpenAI call shape unverified (needs a key) · real embeddings · voice · frontend
