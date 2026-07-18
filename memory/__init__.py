"""Memory layer — Kuzu graph + native vector index.

Foundation for the negotiation agent: one embedded engine holding customers,
deals, calls, patterns and their relationships, plus semantic search.

Public entry point most consumers need:

    from memory.retrieve import get_context, write_call
"""
