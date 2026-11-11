"""Per-node events for the streaming endpoint (/api/ask/stream).

Each graph node that finishes becomes one event: its name, how long it took,
and a few facts from its output that the frontend's live flow panel shows
("Triage: in scope, matched 'AMF'"). Facts are small, JSON-safe and never
include chunk text; the full sources arrive once, in the final `done` event.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List, Optional

# How many matched terms / clauses a fact list carries at most.
_MAX_ITEMS = 5


def _first(items: Optional[List[Any]], n: int = _MAX_ITEMS) -> List[Any]:
    return list(items or [])[:n]


def node_facts(node: str, update: Dict[str, Any]) -> Dict[str, Any]:
    """The facts one node's output contributes to the live flow panel."""
    update = update or {}
    if node == "cache_lookup":
        return {"hit": update.get("cache_hit")}
    if node == "triage":
        signals = update.get("triage_signals") or {}
        matched: List[str] = []
        for terms in signals.values():
            for t in terms:
                if t not in matched:
                    matched.append(t)
        facts: Dict[str, Any] = {
            "decision": update.get("triage_decision"),
            "tier": update.get("triage_tier"),
            "matched": _first(matched),
            "mixed_generation": bool(update.get("mixed_generation")),
        }
        if update.get("mixed_generation"):
            gens = update.get("generation_terms") or {}
            facts["terms_4g"] = _first(gens.get("4g"))
            facts["terms_5g"] = _first(gens.get("5g"))
        return facts
    if node == "retrieve":
        chunks = update.get("chunks") or []
        specs = Counter(c.get("spec_id") for c in chunks if c.get("spec_id"))
        return {
            "count": len(chunks),
            "specs": dict(specs),
            "clauses": _first([f"{c.get('spec_id')} §{c.get('clause_id')}" for c in chunks]),
        }
    if node == "generate":
        return {
            "status": update.get("termination_reason"),
            "unsupported_identifiers": _first(update.get("unsupported_identifiers")),
        }
    if node == "refuse":
        return {"status": update.get("termination_reason") or "out_of_domain"}
    return {}


def sse(event: str, data: Dict[str, Any]) -> str:
    """One Server-Sent Events message."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
