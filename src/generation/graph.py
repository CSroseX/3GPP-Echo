"""The generation graph.

    START -> cache_lookup --hit--> END
                 | miss
                 v
              triage --out_of_domain--> refuse -> END
                 | in_domain (4G/5G-mixed questions get split retrieval queries)
                 v
              retrieve -> generate -> cache_store -> END

cache_lookup + triage form the input guardrail: repeated questions cost no
LLM call, off-topic ones are refused, and cross-generation traps are searched
per generation. generate is the only LLM call for an in-domain question: it
answers from the retrieved chunks and labels its own answer answered /
partial / not_covered, backed by a zero-LLM identifier check
(src/generation/answer_status.py). There is no separate verifier call: it saw
the same chunks as generate, and retrying against the same chunks rarely
changed anything. cache_store keeps only "answered" answers.

Every conditional edge is a pure function in src/generation/routers.py.
"""

from langgraph.graph import END, START, StateGraph

from src.generation.nodes import (
    generate_node,
    make_cache_lookup_node,
    make_cache_store_node,
    make_retrieve_node,
    make_triage_node,
    refuse_node,
)
from src.generation.routers import after_cache, after_triage
from src.generation.state import GraphState
from src.obs.tracing import traced_node


def build_graph(retriever=None, *, embed=None, centroids_loader=None, triage_llm=None, answer_cache=None):
    """Compile the graph.

    retriever: an existing Retriever (app.py / the eval runner cache one);
        constructed lazily on first use otherwise.
    embed: texts -> vectors for triage tier 2. Defaults to the retriever's
        already-loaded BGE model, so triage adds no model load of its own.
    answer_cache: an AnswerCache (src/generation/answer_cache.py), or None
        for no caching. The eval runner passes None so every benchmark
        question runs the full pipeline.
    centroids_loader, triage_llm: test seams; default to the cached
        centroids and the shared LLM client.
    """
    retriever_holder = [retriever]

    def get_retriever():
        if retriever_holder[0] is None:
            from src.retrieval.retriever import Retriever
            retriever_holder[0] = Retriever()
        return retriever_holder[0]

    if embed is None:
        def embed(texts):
            from src.generation.centroids import fastembed_embedder
            return fastembed_embedder(get_retriever().model)(texts)

    workflow = StateGraph(GraphState)

    # Add nodes. Each runs inside its own tracing span (a no-op without
    # LANGFUSE_HOST); wrap the stream in trace_query() so they share a trace.
    nodes = {
        "cache_lookup": make_cache_lookup_node(answer_cache),
        "triage": make_triage_node(embed=embed, centroids_loader=centroids_loader, llm=triage_llm),
        "refuse": refuse_node,
        "retrieve": make_retrieve_node(retriever_factory=get_retriever),
        "generate": generate_node,
        "cache_store": make_cache_store_node(answer_cache),
    }
    for name, node in nodes.items():
        workflow.add_node(name, traced_node(name, node))

    # Add edges
    workflow.add_edge(START, "cache_lookup")
    workflow.add_conditional_edges("cache_lookup", after_cache, {"hit": END, "triage": "triage"})
    workflow.add_conditional_edges("triage", after_triage, {"retrieve": "retrieve", "refuse": "refuse"})
    workflow.add_edge("refuse", END)
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "cache_store")
    workflow.add_edge("cache_store", END)

    return workflow.compile()
