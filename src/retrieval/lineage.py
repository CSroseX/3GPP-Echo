"""Lineage-aware boost: reward a candidate whose clause title (or an
ancestor's) is what the query is asking about.

Q1 asks about "the AMF" and its gold chunk is the clause titled "AMF", yet
the cross-encoder ranked it 18th of 20: the reranker sees only chunk text,
never the heading it sits under. The lineage is already in every payload.

lineage_match() is the share of a title's tokens that appear in the query,
taken over the chunk's own title (weight 1.0) and its ancestors (weight
halving per level up), maximised. The retriever adds
lineage_boost * lineage_match to the cross-encoder score.
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Set

from src.retrieval.hybrid import tokenize

# Leading clause number on a lineage entry: "6.2.1 AMF", "4.2.8.1A General".
_CLAUSE_NUMBER_RE = re.compile(r"^[0-9A-Z]+(?:\.[0-9A-Za-z]+)*\s+")
# Crude stemming: "selecting" and "selection" both become "select".
_STEM_LEN = 6
_ANCESTOR_DECAY = 0.5


def _stems(tokens: Iterable[str]) -> Set[str]:
    return {t[:_STEM_LEN] for t in tokens}


def _title_of(lineage_entry: str) -> str:
    return _CLAUSE_NUMBER_RE.sub("", lineage_entry, count=1)


def lineage_match(query: str, clause_title: str, lineage: Sequence[str]) -> float:
    """0.0–1.0: how fully the query names this chunk's clause or an ancestor."""
    query_stems = _stems(tokenize(query))
    if not query_stems:
        return 0.0

    # Own title first, then ancestors from nearest to the root. The last
    # lineage entry is the chunk's own clause, already covered by clause_title.
    titles = [clause_title or ""] + [_title_of(e) for e in reversed(list(lineage)[:-1])]

    best = 0.0
    weight = 1.0
    for title in titles:
        if title and title != "Frontmatter":
            title_stems = _stems(tokenize(title))
            if title_stems:
                best = max(best, weight * len(title_stems & query_stems) / len(title_stems))
        weight *= _ANCESTOR_DECAY
    return best
