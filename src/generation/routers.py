"""Pure conditional-edge functions for the generation graph.

Extracted from graph.py so routing logic is unit-testable without
constructing a LangGraph workflow or touching an LLM client.
"""

from __future__ import annotations

from typing import Any, Dict


def after_triage(state: Dict[str, Any]) -> str:
    """Router after triage: out-of-domain questions go to refuse (no
    retrieval, no generation); everything else, including a fail-open
    triage, goes to retrieve."""
    if state.get("triage_decision") == "out_of_domain":
        return "refuse"
    return "retrieve"


def after_cache(state: Dict[str, Any]) -> str:
    """Router after cache_lookup: a cached answer ends the graph."""
    return "hit" if state.get("cache_hit") else "triage"
