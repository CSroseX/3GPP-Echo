"""Re-exports so `from src.generation.nodes import generate_node, ...` and
`from src.generation import nodes as gen_nodes; gen_nodes.client` keep
working unchanged after nodes.py became the nodes/ package."""

from src.generation.nodes.core import (  # noqa: F401
    BANNED_PHRASE_PATTERNS,
    MODEL_NAME,
    _detect_banned_phrase,
    client,
    generate_node,
)
from src.generation.nodes.guardrail import make_cache_lookup_node, make_cache_store_node  # noqa: F401
from src.generation.nodes.retrieve import make_retrieve_node  # noqa: F401
from src.generation.nodes.triage import make_triage_node, refuse_node  # noqa: F401
