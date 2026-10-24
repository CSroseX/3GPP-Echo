"""End-to-end runs of the compiled graph with every external dependency
faked: retriever, embedder/centroids, the triage LLM seam, the answer cache,
and the shared client's generate call. Asserts the node path each question
takes and how many LLM calls (hence tokens) it spent."""

import types
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.config import get_settings
from src.generation import nodes as gen_nodes
from src.generation.centroids import Centroids
from src.generation.graph import build_graph

DIM = 8


def unit(i):
    v = np.zeros(DIM, dtype=np.float32)
    v[i] = 1.0
    return v


CENTROIDS = Centroids(vectors=np.vstack([unit(0)]), spec_ids=np.array(["23.501"]), clause_ids=np.array(["5.3"]))


def far_embed(texts):
    """Every query is orthogonal to the domain centroid (cosine 0)."""
    return np.vstack([unit(1) for _ in texts])


class FakeClient:
    """Stands in for gen_nodes.client.chat.completions.create: every call is
    a generate call answering with the given STATUS line."""

    def __init__(self, status="answered"):
        self.status = status
        self.generate_calls = 0

    def create(self, **kwargs):
        self.generate_calls += 1
        content = f"The AMF handles registration and connection management.\nSTATUS: {self.status}"
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))])


class FakeLLM:
    def __init__(self, response):
        self.response, self.calls = response, 0

    def __call__(self, messages, **kwargs):
        self.calls += 1
        return self.response(messages) if callable(self.response) else self.response


def chunks(score, n=5):
    return [
        {"spec_id": "23.501", "clause_id": f"6.2.{i}", "score": score, "cross_score": score,
         "content": f"AMF passage {i}"}
        for i in range(1, n + 1)
    ]


def run(graph, query):
    path, state = [], {"query": query}
    for output in graph.stream({"query": query}):
        for node, value in output.items():
            path.append(node)
            state.update(value or {})
    return path, state


@pytest.fixture
def client(monkeypatch):
    get_settings.cache_clear()
    fake = FakeClient()
    monkeypatch.setattr(gen_nodes.client.chat.completions, "create", fake.create)
    return fake


class FakeCache:
    def __init__(self, hit=None):
        self.hit, self.stored = hit, []

    def lookup(self, question):
        return self.hit

    def store(self, question, answer, sources):
        self.stored.append((question, answer, sources))


def make_graph(retriever, triage_llm="no", answer_cache=None):
    tl = FakeLLM(triage_llm)
    graph = build_graph(
        retriever=retriever,
        embed=far_embed,
        centroids_loader=lambda embed: CENTROIDS,
        triage_llm=tl,
        answer_cache=answer_cache,
    )
    return graph, tl


class TestOutOfDomain:
    def test_capital_of_france_ends_at_refuse_with_zero_llm_calls(self, client):
        retriever = MagicMock()
        graph, triage_llm = make_graph(retriever)

        path, state = run(graph, "What is the capital of France?")

        assert path == ["cache_lookup", "triage", "refuse"]
        assert state["termination_reason"] == "out_of_domain"
        assert state["triage_tier"] == "centroid"  # cosine 0 < refuse_below: no LLM needed
        assert client.generate_calls == 0
        assert triage_llm.calls == 0  # zero tokens spent
        retriever.search.assert_not_called()
        assert state["chunks"] == []
        assert "out of scope" in state["answer"]


class TestAnswerPath:
    def test_happy_path_is_one_llm_call(self, client):
        retriever = MagicMock()
        retriever.search.return_value = chunks(8.0)
        graph, _ = make_graph(retriever)

        path, state = run(graph, "What is the role of the AMF?")

        assert path == ["cache_lookup", "triage", "retrieve", "generate", "cache_store"]
        assert state["termination_reason"] == "answered"
        assert "STATUS" not in state["answer"]
        assert len(state["chunks"]) == 5  # every retrieved chunk reaches generate
        assert client.generate_calls == 1

    def test_partial_answer_ends_without_retry(self, monkeypatch):
        get_settings.cache_clear()
        fake = FakeClient(status="partial")
        monkeypatch.setattr(gen_nodes.client.chat.completions, "create", fake.create)
        retriever = MagicMock()
        retriever.search.return_value = chunks(8.0)
        graph, _ = make_graph(retriever)

        path, state = run(graph, "What is the role of the AMF?")

        assert path == ["cache_lookup", "triage", "retrieve", "generate", "cache_store"]
        assert state["termination_reason"] == "partial"
        assert fake.generate_calls == 1

    def test_empty_retrieval_is_not_covered_with_zero_llm_calls(self, client):
        retriever = MagicMock()
        retriever.search.return_value = []
        graph, _ = make_graph(retriever)

        path, state = run(graph, "What is the role of the AMF?")

        assert path == ["cache_lookup", "triage", "retrieve", "generate", "cache_store"]
        assert state["termination_reason"] == "not_covered"
        assert client.generate_calls == 0


class TestCache:
    def test_hit_ends_the_graph_with_zero_llm_calls(self, client):
        retriever = MagicMock()
        cache = FakeCache(hit={"question": "what is the role of the amf", "answer": "Cached answer.",
                               "sources": [{"spec_id": "23.501", "clause_id": "6.2.1"}],
                               "match": "semantic", "similarity": 0.97})
        graph, triage_llm = make_graph(retriever, answer_cache=cache)

        path, state = run(graph, "What is the role of the AMF ?")

        assert path == ["cache_lookup"]
        assert state["answer"] == "Cached answer."
        assert state["cache_hit"] == "semantic"
        assert client.generate_calls == 0 and triage_llm.calls == 0
        retriever.search.assert_not_called()

    def test_only_answered_answers_are_stored(self, monkeypatch):
        get_settings.cache_clear()
        retriever = MagicMock()
        retriever.search.return_value = chunks(8.0)

        for status, expected_stores in (("answered", 1), ("partial", 0), ("not_covered", 0)):
            fake = FakeClient(status=status)
            monkeypatch.setattr(gen_nodes.client.chat.completions, "create", fake.create)
            cache = FakeCache()
            graph, _ = make_graph(retriever, answer_cache=cache)
            run(graph, "What is the role of the AMF?")
            assert len(cache.stored) == expected_stores


class TestMixedGeneration:
    def test_4g_5g_question_is_split_and_flagged_for_generate(self, client, monkeypatch):
        """Golden-set Q7: an EPS entity (MME) and a 5G one (UDM) in one
        question. Triage splits retrieval per generation and generate is told
        to explain the mismatch, at zero extra LLM cost."""
        prompts = []
        create = client.create

        def spy(**kwargs):
            prompts.append(kwargs["messages"][1]["content"])
            return create(**kwargs)

        monkeypatch.setattr(gen_nodes.client.chat.completions, "create", spy)
        retriever = MagicMock()
        retriever.search.return_value = chunks(8.0)
        graph, _ = make_graph(retriever)

        path, state = run(graph, "When an MME receives an Attach Request, does it communicate with the UDM?")

        assert state["mixed_generation"] is True
        assert "MME" in state["generation_terms"]["4g"] and "UDM" in state["generation_terms"]["5g"]
        assert retriever.search.call_count == 2  # one 4G query, one 5G query
        assert "24.301" in retriever.search.call_args_list[0].args[0]
        assert "<NOTE>" in prompts[0] and "MME" in prompts[0]

    def test_single_generation_question_is_not_split(self, client):
        retriever = MagicMock()
        retriever.search.return_value = chunks(8.0)
        graph, _ = make_graph(retriever)

        path, state = run(graph, "What is the role of the AMF?")

        assert not state.get("mixed_generation")
        assert retriever.search.call_count == 1
