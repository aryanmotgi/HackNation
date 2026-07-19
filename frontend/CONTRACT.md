# Frontend build contract (READ FIRST)

Two views share one backend and one stylesheet. Build ONLY your assigned files.
Do NOT edit `app.py`, `static/styles.css`, or the other view's files.

## Theme rules (non-negotiable — the design system is already in styles.css)
- Green / white / black, LIGHT theme. Use existing CSS variables & classes ONLY.
- Green = accent/success. **Red is for escalation ONLY** (Charlie). Never red elsewhere.
- All numbers (prices, scores, counts) use `.mono` / `.num` (mono + tabular figures).
- Fonts already loaded (Schibsted Grotesk + IBM Plex Mono). Don't add fonts.
- No new colors, no gradients, no inline styles for color. Reuse component classes below.
- Vanilla HTML/CSS/JS. No frameworks, no CDN scripts, no build step.

## Shared nav markup (put at top of <body> on BOTH pages; set `--active` on current)
```html
<nav class="nav">
  <div class="nav__brand"><span class="nav__mark"></span> Lowball · Sales Desk</div>
  <div class="nav__links">
    <a class="nav__link nav__link--active" href="/">Dashboard</a>
    <a class="nav__link" href="/messaging">Messaging</a>
  </div>
  <div class="nav__spacer"></div>
  <span id="mode-tag" class="mode-tag"><span class="mode-tag__dot"></span> …</span>
</nav>
```
Set mode-tag text to `LIVE · <model>` or `MOCK` from `data.model_mode`; add class
`mode-tag--mock` when mock.

## API (fetch from same origin)
- `GET /api/sessions` → snapshot (below). Use on load.
- `POST /api/refresh` → rebuilds (reseed + re-run) and returns the same shape. Wire to a "↻ Replay" button.

### Snapshot shape
```jsonc
{
  "model_mode": "mock",            // or "live"
  "model": "gpt-5.6-terra",
  "metrics": {
    "active_negotiations": 3, "deals_won": 3,
    "avg_price_capture": 0.73, "needs_human": 1, "total": 4
  },
  "customers": [ /* session objects, order: alpha, bravo, charlie, delta */ ]
}
```

### Session object
```jsonc
{
  "customer_id": "cust_alpha",
  "name": "Alpha Textiles",
  "style": "hard_haggler",         // hard_haggler | responsive | goes_silent
  "label": "Hard haggler",
  "product": "Cotton T-shirts 10k units",
  "floor": 3.2, "target": 4.0, "currency": "USD",
  "turns": 3, "agreed_price": 3.68,
  "result": "closed",              // closed | escalated | no_deal
  "status": "won",                 // won | needs-human | active
  "outcome_score": 0.74, "price_capture": 0.6, "sentiment": 0.54,
  "guardrail_hits": 3, "escalate_flag": false,
  "summary": "Closed … at 3.68 …",
  "memory": {
    "style": "hard_haggler", "region": "Guangzhou", "risk_flags": ["price_sensitive"],
    "winning_tactics": [{"pattern_id","label","description","weight","source"}],  // source: "self"|"lookalike"
    "lookalikes": [{"id","name","style","weight"}],
    "past_calls": [{"id","ts","summary","sentiment","outcome_score"}]   // newest first
  },
  "events": [
    {"speaker":"agent","message":"…","reasoning":"…","offer_price":4.32,"intent":"counter","guardrails":["GUARDRAIL: appended a next step."]},
    {"speaker":"customer","message":"…","counter_price":3.2,"accepted":false,"walked":false}
    // intent: counter | accept | hold | handoff
  ]
}
```

## Style → badge class map
`hard_haggler`→`badge--hard`, `responsive`→`badge--responsive`, `goes_silent`→`badge--silent`.
## Status → pill class map
`won`→`pill--won`, `active`→`pill--active`, `needs-human`→`pill--needs-human`.

## Available component classes (all defined in styles.css — use these)
Layout: `.page`, `.page--wide`, `.eyebrow`, `.h1`, `.sub`, `.section-head`, `.section-title`, `.btn`, `.btn--ghost`
Dashboard: `.metrics` + `.tile` (`.tile--alert`, `.tile--neutral`) + `.tile__label/__value(/--alert)/__foot`;
  `.card-grid` + `.card`(`.card--alert`) + `.card__top/__name/__region/__row/__deal/__meta/__scorebar/__scorefill`;
  `.badge`, `.pill`; drawer: `.panel-backdrop`, `.panel`(`.open`), `.panel__close`, `.memrow`(`__k`,`__v`), `.tactic`(`__dot`,`__src`), `.callitem`(`--decline`,`__meta`,`__summary`), `.score-chip`(`--lo`,`--hi`)
Messaging: `.board`, `.thread`(`--alert`), `.thread__head/__name/__deal/__body`, `.bubble`(`--agent`,`--customer`,`__who`), `.turn`(`--customer`), `.reason`, `.chips`, `.chip`(`--offer`,`--guardrail`,`--counter`), `.escalation-banner`(`__icon`), `.outcome-strip`(`__label`,`__score`)
