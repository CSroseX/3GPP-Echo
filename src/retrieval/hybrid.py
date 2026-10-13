"""In-process BM25 over the chunk files, fused with dense results via
Reciprocal Rank Fusion.

Dense BGE embeddings miss exact-acronym queries (NSSAI, T3412, S-NSSAI):
the lexical match is the whole signal there. BM25 over ~2,644 chunks is
cheap enough to hold in memory next to the clause-id set the retriever
already loads. Qdrant-native sparse vectors would do the same inside the
vector DB but need a reindex — future work.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from rank_bm25 import BM25Okapi

# Lowercased alphanumeric runs: "S-NSSAI" → ["s", "nssai"], "T3412" → ["t3412"],
# so a query for "NSSAI" still matches chunks that only say "S-NSSAI".
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Generic English function words plus question framing ("what is", "how
# does"). Not a domain list: without it a question's framing words dominate
# the BM25 score of short chunks.
_STOPWORDS = frozenset("""
a an and are as at be by can do does for from how in is it its of on or
that the their this to used uses what when where which who why will with
""".split())


def tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def chunk_text(chunk: Dict[str, Any]) -> str:
    """Same lineage header the indexer prepends before embedding, plus the
    content; table grids are flattened cell by cell."""
    content = chunk.get("content", "")
    if isinstance(content, list):
        content = " ".join(str(cell) for row in content for cell in row)
    header = f"Spec {chunk['spec_id']} Clause {chunk['clause_id']} {chunk.get('clause_title', '')}"
    return f"{header}\n{content}"


class BM25Index:
    def __init__(self, chunks: Sequence[Dict[str, Any]]):
        self.chunks = list(chunks)
        self._bm25 = BM25Okapi([tokenize(chunk_text(c)) for c in self.chunks])

    def search(
        self,
        query: str,
        k: int,
        spec_id: Optional[str] = None,
        clause_ids: Optional[Iterable[str]] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Top-k (chunk, bm25_score) pairs with a positive score, honouring
        the same spec/clause targeting the dense path filters on."""
        query_tokens = tokenize(query)
        if not query_tokens or k <= 0:
            return []
        allowed = set(clause_ids) if clause_ids is not None else None
        scores = self._bm25.get_scores(query_tokens)

        hits = []
        for i in np.argsort(-scores, kind="stable"):
            if scores[i] <= 0:
                break
            chunk = self.chunks[i]
            if spec_id and chunk["spec_id"] != spec_id:
                continue
            if allowed is not None and chunk["clause_id"] not in allowed:
                continue
            hits.append((chunk, float(scores[i])))
            if len(hits) == k:
                break
        return hits


def rrf_fuse(rankings: Sequence[Sequence[str]], k: int = 60) -> List[str]:
    """Reciprocal Rank Fusion: score(d) = Σ 1 / (k + rank_r(d)) over every
    ranking d appears in. Ties keep first-seen order (earlier rankings win)."""
    scores: Dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda key: -scores[key])
