# Job Spec v2 — the intake → negotiation contract

A **job spec** is the single JSON artifact the intake wizard produces and the
negotiation agent consumes. One file per job: `jobs/<job_id>.json`.

The agent **only negotiates a `status: "confirmed"` spec**. `load_job_spec` rejects
drafts and invalid specs, so un-approved or garbage terms never reach the agent.

The wizard has 5 sections: **Company · Catalog · Guardrails · Voice · Test call**.
v2 adds `company{}`, an extended `deal{}`, richer `hard_rules{}` (thresholds +
escalation toggles), and `voice{}`. New fields are additive — negotiation still reads
`deal` + `hard_rules` exactly as before.

## Full schema

```jsonc
{
  "job_id":     "job_cotton_t_shirts_20260718",
  "created_at": "2026-07-18T12:00:00",
  "source":     "pdf",                    // "pdf" | "voice"
  "status":     "confirmed",              // "draft" | "confirmed" — agent runs ONLY on confirmed

  "company": {                            // step 1
    "name":        "Nova Manufacturing",  // wizard-required
    "website":     "novamfg.com",         // nullable
    "location":    "Shenzhen, China",     // wizard-required
    "timezone":    "Asia/Shanghai",
    "languages":   ["English", "Mandarin"],
    "sales_hours": "09:00–18:00 CST"
  },

  "deal": {                               // step 2 (PDF-parsed, editable)
    "product":        "Cotton T-shirts",  // required
    "sku":            "TS-CTN-180",
    "quantity":       10000,              // int > 0 — minimum order
    "unit":           "units",
    "opening_price":  4.40,               // number ≥ floor
    "target_price":   4.00,               // number ≥ floor
    "floor_price":    3.20,               // number > 0 — HARD floor, agent never quotes below
    "currency":       "USD",
    "volume_tiers":   [{"tier_qty": 5000, "price": 3.80}],
    "lead_time_days": 25,
    "payment_terms":  "30% deposit, 70% before shipment",
    "shipping_terms": "FOB Shenzhen"
  },

  "hard_rules": {                         // step 3
    "floor_price":            3.20,       // MUST equal deal.floor_price (the enforced floor)
    "forbidden_terms":        ["exclusivity", "consignment"],
    "walk_away_price":        null,       // number | null; if set, ≤ floor
    "require_approval_below": 3.20,       // number | null — deals under this need human sign-off
    "transfer_deals_above":   25000,      // number | null — order value that transfers to a human
    "escalation_triggers": [             // subset of the canonical set below
      "price_below_floor", "angry_or_manager", "order_exceeds_transfer_limit"
    ],
    "always_propose_next_step": true
  },

  "voice": {                              // step 4 — STUBBED (ElevenLabs wired server-side later)
    "agent_name":          "Alex",
    "phone":               "+1 (415) 555-0142",
    "voice_style":         "warm_professional",
    "elevenlabs_agent_id": null           // Aryan connects this on the server
  },

  "questions": []                         // optional audit trail of asked questions
}
```

## Canonical escalation triggers (`intake.job_spec.ESCALATION_TRIGGERS`)
`price_below_floor` · `unsupported_customization` · `angry_or_manager` · `order_exceeds_transfer_limit`
(Unknown values are dropped by `build_job_spec`.)

## Validation (`validate_spec` — empty list = valid)

| rule | |
|------|--|
| `deal.product` | present |
| `deal.quantity` | int **> 0** |
| `deal.floor_price` | number **> 0** |
| `deal.target_price` | number **≥ floor** |
| `deal.opening_price` | if set, **≥ floor** |
| `hard_rules.floor_price` | **must equal** `deal.floor_price` |
| `hard_rules.walk_away_price` | null or number **≤ floor** |
| `require_approval_below`, `transfer_deals_above` | null or number ≥ 0 |
| `forbidden_terms`, `escalation_triggers` | lists |
| `status` (loader) | agent **rejects anything but `"confirmed"`** |

`company.name` and `company.location` are **wizard-required** (enforced by
`/api/intake/confirm` when `confirm=true`), not by `validate_spec` — a bare
negotiation spec doesn't need them.

## How `negotiation/` consumes it

```python
from intake.job_spec import load_job_spec
spec = load_job_spec("jobs/<job_id>.json")          # raises if status != confirmed / invalid
# spec["deal"]["floor_price"]                 -> floor clamp (agent._apply_guardrails)
# spec["hard_rules"]["forbidden_terms"]       -> forbidden-phrase guardrail
# spec["hard_rules"]["walk_away_price"]       -> walk-away logic
# spec["hard_rules"]["escalation_triggers"]   -> when to hand to a human
# spec["hard_rules"]["transfer_deals_above"]  -> auto-transfer large orders
```
