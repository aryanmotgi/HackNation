"""Kuzu graph schema — the foundation every other subsystem builds on.

One embedded engine holds the graph AND the vector index (native HNSW), so graph
traversal + semantic search + RAG all live here. No separate vector DB.

Nodes:   Customer, Deal, Call, Pattern
Rels:    HAS_DEAL, HAD_CALL, ABOUT, EXHIBITS, WORKED, SIMILAR_TO

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
