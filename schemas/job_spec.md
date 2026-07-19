# Job Spec — the intake → negotiation contract

A **job spec** is the single JSON artifact the intake wizard produces and the
negotiation agent consumes. One file per job: `jobs/<job_id>.json`.

The agent **only negotiates a `status: "confirmed"` spec**. A `draft` spec is
rejected by the loader (`load_job_spec`) — you cannot negotiate un-approved terms.

## Full schema

```jsonc
{
  "job_id":     "job_cotton_20260718",   // string, unique, slug
  "created_at": "2026-07-18T12:00:00",   // ISO8601
  "source":     "pdf",                    // "pdf" | "voice"
  "status":     "confirmed",              // "draft" | "confirmed" — agent runs ONLY on confirmed

  "deal": {
    "product":        "Cotton T-shirts",  // string, required
    "quantity":       10000,              // int > 0, required
    "unit":           "units",            // string
    "floor_price":    3.20,               // number > 0, required — hard floor
    "target_price":   4.00,               // number ≥ floor_price, required
    "currency":       "USD",              // string
    "payment_terms":  "Net 30"            // string | null
  },

  "hard_rules": {
    "floor_price":              3.20,     // number > 0 — mirrors deal.floor_price (the ENFORCED floor)
    "forbidden_terms":          ["no exclusivity", "no consignment"],  // string[] (may be empty)
    "walk_away_price":          3.00,     // number | null — below this the agent walks
    "escalation_trigger":       "3 declining calls or payment dispute",  // string
    "always_propose_next_step": true      // bool
  },

  "questions": [                          // audit trail: every hard-rule question + its answer
    {"id": "floor_price", "prompt": "…", "answer": "3.20", "source": "pdf"}   // source: pdf | user | voice
  ]
}
```

## Field rules (enforced by `intake/job_spec.py`)

| field | rule |
|-------|------|
| `deal.quantity` | integer **> 0** |
| `deal.floor_price` | number **> 0** |
| `deal.target_price` | number **≥ floor_price** |
| `hard_rules.floor_price` | **must equal** `deal.floor_price` |
| `hard_rules.forbidden_terms` | array (possibly empty) |
| `hard_rules.walk_away_price` | number **or null**; if set, should be **≤ floor_price** |
| `status` | agent loader **rejects anything but `"confirmed"`** |

`validate_spec(spec) -> list[str]` returns human-readable errors (empty = valid).
The confirm screen calls it and **blocks confirmation** on any error, so garbage
parses never reach the agent.

## How `negotiation/` consumes it

```python
from intake.job_spec import load_job_spec
spec = load_job_spec("jobs/job_cotton_20260718.json")   # raises if status != confirmed
# spec["deal"]["floor_price"]          -> floor clamp (agent._apply_guardrails)
# spec["hard_rules"]["forbidden_terms"] -> forbidden-phrase guardrail
# spec["hard_rules"]["walk_away_price"] -> walk-away logic
# spec["hard_rules"]["escalation_trigger"] -> escalation context
```
