"""Kuzu graph schema — the foundation every other subsystem builds on.

One embedded engine holds the graph AND the vector index (native HNSW), so graph
traversal + semantic search + RAG all live here. No separate vector DB.

Nodes:   Customer, Deal, Call, Pattern, Quote
Rels:    HAS_DEAL, HAD_CALL, ABOUT, EXHIBITS, WORKED, SIMILAR_TO, PRODUCED

Live-call additions (voice branch): Customer.phone (inbound caller lookup),
Call.recording_url + Call.transcript (evidence), and a Quote node linked from the
Call that produced it (itemized, comparable quotes for the ranked report). All are
additive — existing readers (get_context/write_call) are unchanged.

Public API:
    connect(db_path)          -> (db, conn)      open/create the database
    create_schema(conn)       create node + rel tables (idempotent)
    build_vector_indexes(conn) build HNSW indexes on Pattern/Call embeddings
                               (call AFTER data is inserted; rebuilds if present)
"""

from __future__ import annotations

import os

import kuzu

from .embeddings import EMBED_DIM

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "kuzu_db")

# Index names, referenced here and in retrieve.py.
PATTERN_INDEX = "pattern_vec_idx"
CALL_INDEX = "call_vec_idx"


def connect(db_path: str = DEFAULT_DB_PATH) -> tuple[kuzu.Database, kuzu.Connection]:
    """Open (or create) the Kuzu database and load the vector extension."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    conn.execute("INSTALL vector;")
    conn.execute("LOAD vector;")
    return db, conn


def create_schema(conn: kuzu.Connection) -> None:
    """Create all node and relationship tables. Idempotent (IF NOT EXISTS)."""
    # --- Node tables ---
    conn.execute(
        """
        CREATE NODE TABLE IF NOT EXISTS Customer(
            id STRING,
            name STRING,
            region STRING,
            negotiation_style STRING,
            risk_flags STRING[],
            phone STRING,
            PRIMARY KEY(id)
        )
        """
    )
    conn.execute(
        f"""
        CREATE NODE TABLE IF NOT EXISTS Deal(
            id STRING,
            product STRING,
            floor_price DOUBLE,
            target_price DOUBLE,
            currency STRING,
            status STRING,
            PRIMARY KEY(id)
        )
        """
    )
    conn.execute(
        f"""
        CREATE NODE TABLE IF NOT EXISTS Call(
            id STRING,
            ts STRING,
            summary STRING,
            sentiment DOUBLE,
            outcome_score DOUBLE,
            embedding FLOAT[{EMBED_DIM}],
            recording_url STRING,
            transcript STRING,
            PRIMARY KEY(id)
        )
        """
    )
    # Quote: the itemized, comparable outcome of a call (drives the ranked report).
    conn.execute(
        """
        CREATE NODE TABLE IF NOT EXISTS Quote(
            id STRING,
            call_id STRING,
            customer_id STRING,
            product STRING,
            unit_price DOUBLE,
            quantity INT64,
            currency STRING,
            fees STRING[],
            terms STRING,
            total DOUBLE,
            sweetener STRING,
            outcome STRING,
            ts STRING,
            PRIMARY KEY(id)
        )
        """
    )
    conn.execute(
        f"""
        CREATE NODE TABLE IF NOT EXISTS Pattern(
            id STRING,
            label STRING,
            detail STRING,
            embedding FLOAT[{EMBED_DIM}],
            PRIMARY KEY(id)
        )
        """
    )

    # --- Relationship tables ---
    conn.execute("CREATE REL TABLE IF NOT EXISTS HAS_DEAL(FROM Customer TO Deal)")
    conn.execute("CREATE REL TABLE IF NOT EXISTS HAD_CALL(FROM Customer TO Call)")
    conn.execute("CREATE REL TABLE IF NOT EXISTS ABOUT(FROM Call TO Deal)")
    conn.execute("CREATE REL TABLE IF NOT EXISTS EXHIBITS(FROM Customer TO Pattern)")
    # WORKED: this tactic (Pattern) produced a good outcome for this Customer.
    conn.execute("CREATE REL TABLE IF NOT EXISTS WORKED(FROM Pattern TO Customer, weight DOUBLE)")
    # SIMILAR_TO: lookalike customers (precomputed in seed for demo reliability).
    conn.execute("CREATE REL TABLE IF NOT EXISTS SIMILAR_TO(FROM Customer TO Customer, weight DOUBLE)")
    # PRODUCED: the Call that produced a Quote (live calls → itemized quote).
    conn.execute("CREATE REL TABLE IF NOT EXISTS PRODUCED(FROM Call TO Quote)")

    # --- Migrations: upgrade an existing DB in place (columns added on the voice
    # branch). Kuzu 0.11 has no ADD COLUMN IF NOT EXISTS, so ignore "already exists".
    _migrate_add_columns(conn)


def _migrate_add_columns(conn: kuzu.Connection) -> None:
    """Add live-call columns to pre-existing tables. Idempotent, safe to re-run."""
    for stmt in (
        "ALTER TABLE Customer ADD phone STRING",
        "ALTER TABLE Call ADD recording_url STRING",
        "ALTER TABLE Call ADD transcript STRING",
    ):
        try:
            conn.execute(stmt)
        except RuntimeError as e:
            msg = str(e).lower()
            if "already exists" not in msg and "already has" not in msg and "duplicate" not in msg:
                raise


def build_vector_indexes(conn: kuzu.Connection) -> None:
    """Build HNSW vector indexes over existing rows. Call AFTER inserting data.

    Kuzu builds each index from the rows present at build time, so this runs once
    at the end of seeding. Persisted indexes are queryable across processes but do
    NOT cleanly drop/recreate on reopen, so we don't rebuild them live — new Call
    rows added later are still reachable via graph queries (get_context), just not
    via Call-level vector search. Re-seeding (reset=True) rebuilds from scratch.

    Idempotent: an 'already exists' error is ignored so a double-call is harmless.
    """
    for table, index, col in (
        ("Pattern", PATTERN_INDEX, "embedding"),
        ("Call", CALL_INDEX, "embedding"),
    ):
        try:
            conn.execute(f"CALL CREATE_VECTOR_INDEX('{table}', '{index}', '{col}')")
        except RuntimeError as e:
            if "already exists" not in str(e):
                raise
