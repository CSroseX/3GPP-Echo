"""Pure conditional-edge functions for the generation graph.

Extracted from graph.py so routing logic is unit-testable without
constructing a LangGraph workflow or touching an LLM client.
"""

from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import END

from src.config import get_settings


def after_triage(state: Dict[str, Any]) -> str:
    """Router after triage: out-of-domain questions go to refuse (no
    retrieval, no generation); everything else, including a fail-open
    triage, goes to retrieve."""
    if state.get("triage_decision") == "out_of_domain":
        return "refuse"
    return "retrieve"


def after_cache(state: Dict[str, Any]) -> str:
    """Router after cache_lookup: a cached verified answer ends the graph."""
    return "hit" if state.get("cache_hit") else "triage"


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
