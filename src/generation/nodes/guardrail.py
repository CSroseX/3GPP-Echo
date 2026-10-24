"""Input guardrail nodes around the answer cache.

cache_lookup runs first: a cache hit ends the graph with the stored answer
and no LLM call. cache_store runs after generate and saves only answers whose
status is "answered" (never partial or not_covered ones).
Both are no-ops when the graph is built without a cache (the eval runner
builds it without one, so benchmark runs always exercise the full pipeline).

The other half of the guardrail, "is this worth answering", lives in triage:
off-topic questions are refused there, and questions that mix 4G and 5G terms
are flagged so retrieval searches each generation separately.
"""

from __future__ import annotations

from typing import Any, Dict

from src.obs.logging import get_logger

log = get_logger(__name__)


def make_cache_lookup_node(cache=None):
    def cache_lookup_node(state: Dict[str, Any]) -> Dict[str, Any]:
        if cache is None:
            return {}
        hit = cache.lookup(state["query"])
        if hit is None:
            return {}
        log.info("cache_lookup_node.hit", query=state["query"], cached_question=hit["question"],
                 match=hit["match"], similarity=hit["similarity"])
        return {
            "answer": hit["answer"],
            "chunks": hit["sources"],
            "cache_hit": hit["match"],
            "termination_reason": "answered",
        }

    return cache_lookup_node


def make_cache_store_node(cache=None):
    def cache_store_node(state: Dict[str, Any]) -> Dict[str, Any]:
        if cache is not None and state.get("termination_reason") == "answered" and state.get("answer"):
            sources = [{"spec_id": c.get("spec_id"), "clause_id": c.get("clause_id")}
                       for c in state.get("chunks") or []]
            cache.store(state["query"], state["answer"], sources)
        return {}

    return cache_store_node
