"""
Vector search backed by pgvector HNSW, fused with the ACL predicate
in a *single* SQL query.

The query below is the heart of the demo: vector similarity + access
control execute atomically inside PostgreSQL – there is no "fetch top-K
then filter in Python" step.
"""

import json
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.retrieval.acl_filter import build_search_sql


def _embedding_str(embedding: np.ndarray | list[float]) -> str:
    vals = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
    return "[" + ", ".join(f"{v:.8f}" for v in vals) + "]"


def search_similar_chunks(
    db: Session,
    query_embedding: np.ndarray | list[float],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fused vector + ACL search.

    Parameters
    ----------
    db
        SQLAlchemy session whose transaction already has the app.* session
        variables set (see app/db/session.py).
    query_embedding
        The question embedding (384-dim for all-MiniLM-L6-v2, normalized).
    limit
        Maximum number of chunks to return.

    Returns
    -------
    List of dicts: {chunk_id, raw_text, exact_locator, source_doc_id, source_type, distance}
    """
    sql = text(build_search_sql(limit=limit))
    params = {"query_embedding": _embedding_str(query_embedding)}

    rows = db.execute(sql, params).mappings().all()

    results: list[dict[str, Any]] = []
    for row in rows:
        locator = row["exact_locator"]
        if isinstance(locator, str):
            locator = json.loads(locator)
        results.append(
            {
                "chunk_id": row["chunk_id"],
                "raw_text": row["raw_text"],
                "exact_locator": locator,
                "source_doc_id": row["source_doc_id"],
                "source_type": row["source_type"],
                "distance": float(row["distance"]),
            }
        )

    return results


# Re-export for convenience
__all__ = ["search_similar_chunks"]
