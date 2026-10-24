"""GraphState: the shape of data threaded through the generation graph."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    # Core fields, populated on every run.
    query: str
    chunks: List[Dict[str, Any]]
    answer: str

    # How the question ended (TERMINATION_REASONS): generate's own status
    # label after the identifier check, or out_of_domain from refuse.
    termination_reason: Optional[str]
    # Identifiers (T3510, #22, ATTACH REQUEST) in the answer that the source
    # text never mentions; any of them downgrades "answered" to "partial".
    unsupported_identifiers: Optional[List[str]]

    # Phase 4 decision-nodes.
    triage_decision: Optional[str]  # in_domain | out_of_domain
    triage_tier: Optional[str]  # lexical | centroid | llm | fail_open
    triage_score: Optional[float]  # max centroid cosine, when tier 2 ran
    triage_signals: Optional[Dict[str, List[str]]]
    retrieval_scores: Optional[List[float]]
    # Input guardrail: cache_lookup sets cache_hit ("exact" | "semantic");
    # triage flags questions that mix 4G and 5G terms and sets the per-
    # generation retrieval_queries that retrieve_node searches on (`query`
    # stays the user's question).
    cache_hit: Optional[str]
    mixed_generation: Optional[bool]
    generation_terms: Optional[Dict[str, List[str]]]
    retrieval_queries: Optional[List[str]]

    # Reserved for later phases; unpopulated today.
    citations: Optional[List[Dict[str, Any]]]


# Valid values for termination_reason once a terminal node is reached.
TERMINATION_REASONS = {
    "answered",  # the source text covers the whole question
    "partial",  # covers part of it, no STATUS line, or an identifier isn't in the sources
    "not_covered",  # covers none of it, retrieval found nothing, or the reply was empty
    "out_of_domain",
}
