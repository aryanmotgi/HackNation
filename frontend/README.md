# Unified manufacturer workspace

The Flask frontend presents the repository's existing intake, negotiation, and Kuzu
memory systems as one manufacturer product. Shared navigation connects agent setup,
overview, a labeled voice rehearsal, real negotiation evidence, customers, and the
real memory graph.

## Run

From the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m frontend.app
```

Open `http://127.0.0.1:5001/`.

## Recommended judge flow

1. Start at **Agent setup** and show company, catalog, pricing, escalation, voice Agent ID, and required AI disclosure.
2. Open **Overview** to show the judge scenario alongside metrics from the real negotiation backend.
3. Open **Live demo**, turn sound on, and run the two-voice rehearsal through the structured sample-pending outcome.
4. Open **Negotiations** to compare hard-haggler, responsive, and staller behavior with reasoning and guardrail evidence.
5. Open **Memory** to show the live Kuzu graph, declining-history escalation, and lookalike tactic transfer.

## Honest integration boundaries

- `/api/sessions`, `/api/refresh`, and `/api/graph` remain the existing real backend interfaces.
- Controlled-format PDF extraction is deterministic and real; arbitrary PDF layouts still need the documented vision fallback.
- `/call` is a fixed browser-speech rehearsal and is labeled on-screen. It does not claim to be a live ElevenLabs call.
- Manufacturers enter an ElevenLabs Agent ID only. API keys stay server-side.
- The OpenAI-backed reasoning path and live voice transport require credentials and are not exercised in the offline demo.

## Verify

```bash
.venv/bin/python -m tests.smoke
.venv/bin/python -m tests.smoke_intake
node --check frontend/static/call.js
node --check frontend/static/dashboard.js
node --check frontend/static/intake.js
node --check frontend/static/messaging.js
node --check frontend/static/graph.js
```
