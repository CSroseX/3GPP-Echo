"""Deterministic chunk ids, shared by the indexer (Qdrant point ids and the
payload's chunk_id) and the retriever's in-process BM25 index, which must
produce the same ids to fuse its hits with Qdrant's."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List


def assign_chunk_ids(chunks: List[Dict[str, Any]]) -> None:
    """Set chunk["chunk_id"] = sha1(spec_id|clause_id|ordinal) in place, where
    ordinal is the chunk's position among chunks sharing the same (spec_id,
    clause_id) — clause_id alone is not unique (e.g. frontmatter chunks all
    share clause_id "0"). Ids depend on list order, so callers must load the
    chunk files in the same (sorted) order the indexer does."""
    clause_ordinals: Dict[tuple, int] = {}
    for chunk in chunks:
        key = (chunk["spec_id"], chunk["clause_id"])
        ordinal = clause_ordinals.get(key, 0)
        clause_ordinals[key] = ordinal + 1
        chunk["chunk_id"] = hashlib.sha1(
            f"{chunk['spec_id']}|{chunk['clause_id']}|{ordinal}".encode("utf-8")
        ).hexdigest()


def point_id_for(chunk_id: str) -> str:
    """Qdrant point ids must be an unsigned int or a UUID string; derive a
    stable UUID from the chunk_id digest so the point id is reproducible."""
    d = chunk_id
    return f"{d[:8]}-{d[8:12]}-{d[12:16]}-{d[16:20]}-{d[20:32]}"
