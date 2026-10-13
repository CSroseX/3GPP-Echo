"""Pure conditional-edge functions for the generation graph.

Extracted from graph.py so routing logic is unit-testable without
constructing a LangGraph workflow or touching an LLM client.
"""

from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import END

from src.config import get_settings


def after_retrieve(state: Dict[str, Any]) -> str:
    """Router after the retrieve node: skip LLM calls when retrieval
    found nothing (mirrors the old pre-graph empty-chunks check)."""
    if not state.get("chunks"):
        return "abstain"
    return "generate"


def after_rewrite(state: Dict[str, Any]) -> str:
    """Router after rewrite_query: re-retrieve on the rewritten query, unless
    the rewrite was a no-op (cap already spent, or it reproduced the queries
    already tried) — an identical retrieval can't change the grade."""
    if state.get("rewrite_noop"):
        return "abstain"
    return "retrieve"


def should_retry(state: Dict[str, Any]) -> str:
    """Router for the `verify` node's conditional edges.

    - verification_passed -> END
    - verifier couldn't run (transport failure) -> flag_unverified immediately;
      retrying against an unavailable verifier cannot succeed and would burn
      the grounding-retry budget on an operational failure, not a grounding one.
    - grounding_retries exhausted -> flag_unverified
    - otherwise -> generate (another grounding attempt)
    """
    if state.get("verification_passed"):
        return END

    if state.get("termination_reason") == "verifier_unavailable":
        return "flag_unverified"

    grounding_retries = state.get("grounding_retries", state.get("retries", 0))
    if grounding_retries >= get_settings().max_retries:
        return "flag_unverified"

    return "generate"
