"""Embedding function — the 'search brain'.

STUB IMPLEMENTATION: deterministic, offline, no real semantics. It produces a
stable 384-dim vector from text so the pipeline runs end to end without a model.

SWAP BEFORE DEMO for real semantic matching. Because EMBED_DIM already equals the
real model's dim (384 = all-MiniLM-L6-v2), swapping requires NO schema change:

    # TODO(demo): swap for real model
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    def embed(text: str) -> list[float]:
        return _model.encode(text, normalize_embeddings=True).tolist()

Everything else in memory/ calls embed() and never touches the internals.
"""

from __future__ import annotations

import hashlib
import math

# Dimensionality of every embedding. Matches all-MiniLM-L6-v2 so the real model
# drops in without touching schema.py's FLOAT[EMBED_DIM] columns.
EMBED_DIM = 384


def embed(text: str) -> list[float]:
    """Return a stable, L2-normalized EMBED_DIM vector for `text`.

    STUB: hash-seeded pseudo-random projection. Deterministic (same text -> same
    vector) so seeds are reproducible, but NOT semantically meaningful. Similar
    wording does not yield similar vectors. Replace before the demo.
    """
    text = (text or "").strip().lower()
    vec: list[float] = []
    counter = 0
    # Expand the text hash into EMBED_DIM floats in [-1, 1].
    while len(vec) < EMBED_DIM:
        h = hashlib.sha256(f"{text}|{counter}".encode()).digest()
        for i in range(0, len(h), 2):
            if len(vec) >= EMBED_DIM:
                break
            word = (h[i] << 8) | h[i + 1]          # 0..65535
            vec.append((word / 32767.5) - 1.0)      # -1..1
        counter += 1
    # L2 normalize so cosine/L2 distance behaves.
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]
