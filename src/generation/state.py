"""GraphState: the shape of data threaded through the generate/verify graph."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    # Core fields, populated on every run.
    query: str
    chunks: List[Dict[str, Any]]
    answer: str
    verification_passed: bool
    feedback: str
    retries: int  # legacy counter kept for app.py / eval scripts; see `attempt`

    # Phase 2: truthful counters and typed termination state.
    attempt: int
    grounding_retries: int
    transport_attempts: int
    termination_reason: Optional[str]
    abstention: Optional[Dict[str, Any]]  # set by abstain_node on any non-verified exit

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
    "verified",
    "verification_failed",
    "insufficient_context",  # retrieval returned no chunks
    "out_of_domain",
    "verifier_unavailable",
}
