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
]

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
     "Deadline nudge landed; Alpha agreed to a smaller concession than last time.", 0.4, 0.70),

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

    for cid, name, region, style, flags in CUSTOMERS:
        conn.execute(
            "CREATE (:Customer {id:$id, name:$name, region:$region, "
            "negotiation_style:$style, risk_flags:$flags})",
            {"id": cid, "name": name, "region": region, "style": style, "flags": flags},
        )

    for did, product, floor, target, currency, status, cid in DEALS:
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

    for cid, pid in EXHIBITS:
        conn.execute(
            "MATCH (c:Customer {id:$cid}), (p:Pattern {id:$pid}) CREATE (c)-[:EXHIBITS]->(p)",
            {"cid": cid, "pid": pid},
        )

    for pid, cid, weight in WORKED:
        conn.execute(
            "MATCH (p:Pattern {id:$pid}), (c:Customer {id:$cid}) "
            "CREATE (p)-[:WORKED {weight:$w}]->(c)",
            {"pid": pid, "cid": cid, "w": weight},
        )

    for a, b, weight in SIMILAR:
        conn.execute(
            "MATCH (x:Customer {id:$a}), (y:Customer {id:$b}) "
            "CREATE (x)-[:SIMILAR_TO {weight:$w}]->(y)",
            {"a": a, "b": b, "w": weight},
        )

    for kid, cid, did, ts, summary, sentiment, score in CALLS:
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
    print(f"Seeded {len(CUSTOMERS)} customers, {len(DEALS)} deals, "
          f"{len(PATTERNS)} patterns, {len(CALLS)} calls -> {db_path}")


if __name__ == "__main__":
    seed()
