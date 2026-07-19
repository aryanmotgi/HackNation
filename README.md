# Loomhaus — memory-driven negotiation agent (manufacturer side)

A B2B negotiation AI for manufacturers. A manufacturer has thousands of customers who
each negotiate differently — some grind hard, some agree fast, some stall. The agent
negotiates with each one, **remembers every customer**, and adapts its approach from
that memory. Built for HackNation (tracks: **haggle · compare · call**).

The differentiator is **memory**: a Kuzu graph + native vector index in one engine.
Everything connects — customers, deals, calls, tactics — and that graph makes the agent
smarter per customer. This is **retrieval-augmented adaptation, not model training**: the
agent adapts per customer from memory; the model itself is never retrained.

## Architecture

```
memory/        Kuzu graph + vector index — the foundation. get_context() / write_call().
negotiation/   The agent, the customer bot, scoring, the arena loop, terminal demo.
frontend/      Unified Flask workspace: intake, dashboard, voice demo, negotiations, memory.
tests/         End-to-end negotiation and intake smoke tests.
```

```
Customer ──HAS_DEAL──▶ Deal ◀──ABOUT── Call ◀──HAD_CALL── Customer
   │                                                          
   ├─EXHIBITS─▶ Pattern ─WORKED─▶ Customer      (tactics that worked)
   └─SIMILAR_TO─▶ Customer                       (lookalikes → tactic transfer)
```

Before a negotiation the agent calls `get_context(customer)` → style, floor price,
past-call summaries, winning tactics (incl. tactics transferred from lookalike
customers), and an escalation flag. After, `write_call()` stores a short summary +
outcome score. A run of declining scores → the agent hands off to a human.

## Setup

```bash
python3.12 -m venv .venv           # kuzu has no wheel for 3.14 yet — use 3.12
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m memory.seed    # build the graph with demo data
```

Optional — go live (otherwise an offline mock runs, deterministic):
```bash
cp .env.example .env               # add OPENAI_API_KEY (model: gpt-5.6-terra)
```

## Run

**Terminal demo** — watch the agent negotiate all 3 styles, reasoning printed each turn:
```bash
.venv/bin/python -m negotiation.demo
```

**Manufacturer workspace** — every user-facing flow on one server:
```bash
.venv/bin/python -m frontend.app
#   http://127.0.0.1:5001/            manufacturer setup + controlled PDF extraction
#   http://127.0.0.1:5001/dashboard   overview, live backend metrics, approvals, customers
#   http://127.0.0.1:5001/call        labeled two-voice judge rehearsal + structured result
#   http://127.0.0.1:5001/messaging   turn-by-turn negotiation evidence across 3 styles
#   http://127.0.0.1:5001/graph       live 3D Kuzu memory graph
```

**Smoke test** — verify the whole stack (no API key needed):
```bash
.venv/bin/python -m tests.smoke
.venv/bin/python -m tests.smoke_intake
```

## The demo in one minute

Same product for everyone — **Cotton T-shirts, floor 3.20 / target 4.00 USD**. Only the
customer changes, so the outcome differences come purely from adaptation:

| customer | style | what the agent does | outcome |
|----------|-------|--------------------|---------|
| Alpha Textiles | hard haggler | anchors high, grinds, holds above floor 3.20 | closes 3.68 |
| Bravo Imports | responsive | rapport, closes fast near target | closes 4.16 |
| Charlie Retail | staller | sees declining history → **escalates to human** | handed off |
| Delta Fashion | lookalike | wins using a tactic **transferred from Alpha** | closes 3.68 |

Guardrails are enforced in code, not left to the model: never quote below floor,
always propose a next step, escalate on declining outcomes.

The **Live demo** route adds a separate, clearly labeled rehearsal for the voice-call
track: Nova Manufacturing negotiates with Maya Chen at West Coast Goods for custom
500 ml bottles. It demonstrates a $5.20 opening, $4.80 target, $4.45 floor, an approved
5,000-unit trade at $4.60, 25-day lead time, AI disclosure, and a sample-pending result.
The script and browser voices are fixtures; the page never represents them as a live
ElevenLabs call.

## Before the demo
- **Swap the embedder** — `memory/embeddings.py` is a stub (deterministic, not semantic).
  `get_context` (graph) is fully real now; `search_patterns` (vectors) is noise until you
  drop in `all-MiniLM-L6-v2`. `EMBED_DIM=384` already matches it → no schema change.
- **Add `OPENAI_API_KEY`** to make the reasoning model-generated (mock proves the logic).

## Status
- ✅ Kuzu memory, negotiation arena, guardrails, escalation, scoring, and intake job spec
- ✅ unified responsive manufacturer workspace with honest demo/live boundaries
- ✅ 25 negotiation checks + 15 intake checks passing offline
- ⏳ live OpenAI call verification (needs a key) · live ElevenLabs transport · arbitrary-PDF vision extraction
