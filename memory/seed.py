"""Seed the graph with demo data.

Creates 4 customers (one per negotiation style + a hard-haggler lookalike pair),
their open deals, reusable tactic patterns, and call history. Charlie's calls
decline in outcome score to trigger the escalation flag.

Run:  python -m memory.seed
"""

from __future__ import annotations

import os
import shutil

from .embeddings import embed
from .schema import DEFAULT_DB_PATH, build_vector_indexes, connect, create_schema

# Extra procedurally-generated accounts stacked on top of the 4 hand-authored
# customers below. The demo negotiation/dashboard only touch the named 4; these
# exist purely to give the 3D memory graph real density — a connected ball of
# hundreds of nodes instead of a sparse handful. Deterministic (no RNG) so the
# layout is stable across rebuilds.
GEN_COUNT = 44

# --- Demo data ---------------------------------------------------------------

CUSTOMERS = [
    # id, name, region, style, risk_flags
    ("cust_alpha", "Alpha Textiles", "Guangzhou", "hard_haggler", ["price_sensitive"]),
    ("cust_bravo", "Bravo Imports", "Berlin", "responsive", []),
    ("cust_charlie", "Charlie Retail", "Lagos", "goes_silent", ["slow_payer"]),
    ("cust_delta", "Delta Fashion", "Guangzhou", "hard_haggler", ["price_sensitive"]),
]

DEALS = [
    # id, product, floor, target, currency, status, customer_id
    # One product line across every customer (same unit economics) — only the
    # customer's negotiation style differs, so the demo isolates adaptation.
    ("deal_alpha", "Cotton T-shirts · 10k units", 3.20, 4.00, "USD", "open", "cust_alpha"),
    ("deal_bravo", "Cotton T-shirts · 6k units", 3.20, 4.00, "USD", "open", "cust_bravo"),
    ("deal_charlie", "Cotton T-shirts · 5k units", 3.20, 4.00, "USD", "open", "cust_charlie"),
    ("deal_delta", "Cotton T-shirts · 8k units", 3.20, 4.00, "USD", "open", "cust_delta"),
]

PATTERNS = [
    # id, label, description
    ("pat_anchor", "Anchor high", "Open above target price and concede slowly in small steps."),
    ("pat_bundle", "Bundle upsell", "Offer a volume discount to grow order size instead of cutting unit price."),
    ("pat_silence", "Patient silence", "Let the customer speak first; do not fill pauses or negotiate against yourself."),
    ("pat_deadline", "Deadline nudge", "Cite limited production-slot availability to create urgency."),
    ("pat_rapport", "Rapport build", "Open with relationship framing and small talk before numbers."),
    # Extra tactics — shared across the generated accounts so patterns act as
    # cross-links that pull the graph into one dense web.
    ("pat_split", "Split the difference", "Meet halfway once, then hold firm to signal a real floor."),
    ("pat_terms", "Trade on terms", "Give ground on payment or lead time to protect the unit price."),
    ("pat_scarcity", "Fabric scarcity", "Frame cotton lot availability as limited to justify holding price."),
    ("pat_loyalty", "Loyalty framing", "Reference prior orders to earn a smaller concession this round."),
    ("pat_walkaway", "Credible walk-away", "Signal willingness to pass on the deal to reset an aggressive anchor."),
]

# --- Procedural fleet of extra accounts (graph density only) -----------------

_GEN_STYLES = ["hard_haggler", "responsive", "goes_silent"]
_GEN_REGIONS = ["Guangzhou", "Berlin", "Lagos", "Ho Chi Minh City", "Istanbul",
                "Dhaka", "São Paulo", "Los Angeles", "Milan", "Bangkok",
                "Cairo", "Mumbai", "Warsaw", "Toronto", "Manila"]
_GEN_PREFIX = ["Nimbus", "Cedar", "Orion", "Vertex", "Harbor", "Quill", "Sable",
               "Onyx", "Willow", "Marlowe", "Halcyon", "Pike", "Juno", "Ridge",
               "Ember", "Solace", "Fenwick", "Larkspur", "Meridian", "Cobalt",
               "Thistle", "Vantage"]
_GEN_SUFFIX = ["Textiles", "Imports", "Apparel", "Trading", "Garments",
               "Wholesale", "Retail", "Sourcing", "Mills", "Collective"]
_GEN_QTY = [4000, 5000, 6000, 7500, 8000, 9000, 10000, 12000, 15000]
_GEN_PAT = ["pat_anchor", "pat_bundle", "pat_silence", "pat_deadline",
            "pat_rapport", "pat_split", "pat_terms", "pat_scarcity",
            "pat_loyalty", "pat_walkaway"]
_GEN_SUMMARIES = {
    "hard_haggler": [
        "Pushed hard on unit price; anchoring held margin near target.",
        "Grinding on price again; conceded one small step, no more.",
        "Threatened to walk; credible walk-away reset the anchor.",
    ],
    "responsive": [
        "Warm call; receptive after rapport, close to accepting target.",
        "Agreeable on terms; volume bundle landed cleanly.",
        "Quick to confirm; loyalty framing shaved the concession.",
    ],
    "goes_silent": [
        "Mostly silent on price; polite but noncommittal.",
        "Long pauses; deflected on payment terms.",
        "Went cold, hinted at a competitor quote, no movement.",
    ],
}


def _pick(seq, i):
    return seq[i % len(seq)]


def generate_fleet(n: int = GEN_COUNT):
    """Deterministically build n extra customers with deals, calls, pattern
    links and lookalike clusters. Returns parallel lists matching the shapes of
    the hand-authored CUSTOMERS/DEALS/CALLS/EXHIBITS/WORKED/SIMILAR tables."""
    customers, deals, calls = [], [], []
    exhibits, worked, similar = [], [], []
    prev_by_style: dict[str, str] = {}

    for i in range(n):
        cid = f"cust_gen_{i:02d}"
        style = _pick(_GEN_STYLES, i)
        region = _pick(_GEN_REGIONS, i * 3 + 1)
        name = f"{_pick(_GEN_PREFIX, i)} {_pick(_GEN_SUFFIX, i * 2 + 1)}"
        flags = ["price_sensitive"] if style == "hard_haggler" else (
            ["slow_payer"] if style == "goes_silent" else [])
        customers.append((cid, name, region, style, flags))

        did = f"deal_gen_{i:02d}"
        qty = _pick(_GEN_QTY, i)
        deals.append((did, f"Cotton T-shirts · {qty // 1000}k units",
                      3.20, 4.00, "USD", "open", cid))

        # 1-3 calls per customer, dates fanned across July
        n_calls = 1 + (i % 3)
        base_sent = {"hard_haggler": 0.1, "responsive": 0.6, "goes_silent": -0.2}[style]
        for j in range(n_calls):
            kid = f"call_gen_{i:02d}_{j}"
            day = 5 + ((i + j * 2) % 20)
            ts = f"2026-07-{day:02d}T{9 + j:02d}:00:00"
            summary = _pick(_GEN_SUMMARIES[style], j)
            sent = round(base_sent + 0.1 * j, 2)
            # goes_silent trends downward -> some flip to escalation
            score = round(max(0.2, 0.65 - (0.12 * j if style == "goes_silent" else -0.05 * j)), 2)
            calls.append((kid, cid, did, ts, summary, sent, score))

        # each customer exhibits one pattern and one worked on them
        exhibits.append((cid, _pick(_GEN_PAT, i)))
        worked.append((_pick(_GEN_PAT, i * 2 + 3), cid, round(0.6 + 0.03 * (i % 10), 2)))

        # lookalike chain within the same style -> dense SIMILAR_TO web
        prev = prev_by_style.get(style)
        if prev:
            w = round(0.78 + 0.02 * (i % 6), 2)
            similar.append((prev, cid, w))
            similar.append((cid, prev, w))
        prev_by_style[style] = cid

    return customers, deals, calls, exhibits, worked, similar

# Customer EXHIBITS Pattern (behavior the customer displays)
EXHIBITS = [
    ("cust_alpha", "pat_anchor"),
    ("cust_delta", "pat_anchor"),
    ("cust_charlie", "pat_silence"),
    ("cust_bravo", "pat_rapport"),
]

# Pattern WORKED on Customer (tactic that produced a good outcome), weight
WORKED = [
    ("pat_deadline", "cust_alpha", 0.8),
    ("pat_bundle", "cust_delta", 0.7),
    ("pat_rapport", "cust_bravo", 0.9),
    ("pat_silence", "cust_charlie", 0.6),
]

# SIMILAR_TO lookalikes (precomputed, bidirectional), weight
SIMILAR = [
    ("cust_alpha", "cust_delta", 0.86),
    ("cust_delta", "cust_alpha", 0.86),
]

# Calls: id, customer, deal, ts, summary, sentiment, outcome_score
CALLS = [
    ("call_alpha_1", "cust_alpha", "deal_alpha", "2026-07-11T09:00:00",
     "Alpha pushed hard on unit price; held near target after anchoring high.", 0.1, 0.50),
    ("call_alpha_2", "cust_alpha", "deal_alpha", "2026-07-15T09:00:00",
     "Deadline nudge landed; closed at 3.85 per unit with priority freight included — "
     "Alpha was happy with the freight and the fast lead time.", 0.4, 0.70),

    ("call_bravo_1", "cust_bravo", "deal_bravo", "2026-07-12T14:00:00",
     "Warm call; Bravo responsive after rapport, close to accepting target.", 0.7, 0.80),

    # Charlie: strictly declining outcome -> escalation
    ("call_charlie_1", "cust_charlie", "deal_charlie", "2026-07-10T11:00:00",
     "Charlie mostly silent on price; polite but noncommittal.", 0.0, 0.60),
    ("call_charlie_2", "cust_charlie", "deal_charlie", "2026-07-13T11:00:00",
     "Longer silences; Charlie deflected on payment terms.", -0.2, 0.45),
    ("call_charlie_3", "cust_charlie", "deal_charlie", "2026-07-16T11:00:00",
     "Charlie went cold, hinted at competitor quote, no movement.", -0.5, 0.30),

    ("call_delta_1", "cust_delta", "deal_delta", "2026-07-09T08:00:00",
     "Delta anchored aggressively; bundle upsell kept margin intact.", 0.2, 0.60),
    ("call_delta_2", "cust_delta", "deal_delta", "2026-07-14T08:00:00",
     "Second round steady; Delta receptive to volume bundle.", 0.3, 0.65),
]


# --- Seeding -----------------------------------------------------------------

def seed(db_path: str = DEFAULT_DB_PATH, reset: bool = True) -> None:
    """Build the database from scratch. reset=True wipes any existing db first."""
    if reset:
        # Kuzu may store the db as a single file or a directory, plus a .wal
        # sidecar. Clear whatever form exists so the seed is a clean rebuild.
        for path in (db_path, f"{db_path}.wal"):
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.exists(path):
                os.remove(path)

    db, conn = connect(db_path)
    create_schema(conn)

    # Merge hand-authored demo data with the generated fleet for graph density.
    gen_c, gen_d, gen_k, gen_ex, gen_w, gen_s = generate_fleet(GEN_COUNT)
    customers = CUSTOMERS + gen_c
    deals = DEALS + gen_d
    calls = CALLS + gen_k
    exhibits = EXHIBITS + gen_ex
    worked = WORKED + gen_w
    similar = SIMILAR + gen_s

    for cid, name, region, style, flags in customers:
        conn.execute(
            "CREATE (:Customer {id:$id, name:$name, region:$region, "
            "negotiation_style:$style, risk_flags:$flags})",
            {"id": cid, "name": name, "region": region, "style": style, "flags": flags},
        )

    for did, product, floor, target, currency, status, cid in deals:
        conn.execute(
            "CREATE (:Deal {id:$id, product:$product, floor_price:$floor, "
            "target_price:$target, currency:$currency, status:$status})",
            {"id": did, "product": product, "floor": floor, "target": target,
             "currency": currency, "status": status},
        )
        conn.execute(
            "MATCH (c:Customer {id:$cid}), (d:Deal {id:$did}) CREATE (c)-[:HAS_DEAL]->(d)",
            {"cid": cid, "did": did},
        )

    for pid, label, desc in PATTERNS:
        conn.execute(
            "CREATE (:Pattern {id:$id, label:$label, detail:$dtl, embedding:$emb})",
            {"id": pid, "label": label, "dtl": desc, "emb": embed(f"{label}. {desc}")},
        )

    for cid, pid in exhibits:
        conn.execute(
            "MATCH (c:Customer {id:$cid}), (p:Pattern {id:$pid}) CREATE (c)-[:EXHIBITS]->(p)",
            {"cid": cid, "pid": pid},
        )

    for pid, cid, weight in worked:
        conn.execute(
            "MATCH (p:Pattern {id:$pid}), (c:Customer {id:$cid}) "
            "CREATE (p)-[:WORKED {weight:$w}]->(c)",
            {"pid": pid, "cid": cid, "w": weight},
        )

    for a, b, weight in similar:
        conn.execute(
            "MATCH (x:Customer {id:$a}), (y:Customer {id:$b}) "
            "CREATE (x)-[:SIMILAR_TO {weight:$w}]->(y)",
            {"a": a, "b": b, "w": weight},
        )

    for kid, cid, did, ts, summary, sentiment, score in calls:
        conn.execute(
            "CREATE (:Call {id:$id, ts:$ts, summary:$summary, sentiment:$sent, "
            "outcome_score:$score, embedding:$emb})",
            {"id": kid, "ts": ts, "summary": summary, "sent": sentiment,
             "score": score, "emb": embed(summary)},
        )
        conn.execute(
            "MATCH (c:Customer {id:$cid}), (k:Call {id:$kid}) CREATE (c)-[:HAD_CALL]->(k)",
            {"cid": cid, "kid": kid},
        )
        conn.execute(
            "MATCH (k:Call {id:$kid}), (d:Deal {id:$did}) CREATE (k)-[:ABOUT]->(d)",
            {"kid": kid, "did": did},
        )

    build_vector_indexes(conn)
    print(f"Seeded {len(customers)} customers, {len(deals)} deals, "
          f"{len(PATTERNS)} patterns, {len(calls)} calls -> {db_path}")


if __name__ == "__main__":
    seed()
