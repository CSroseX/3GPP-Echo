"""Public API (src/api/main.py), driven with a fake graph: no models, Qdrant or LLM."""

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


class FakeGraph:
    def __init__(self, result=None, error=None):
        self.result = result or {}
        self.error = error
        self.queries = []

    def invoke(self, inputs):
        self.queries.append(inputs["query"])
        if self.error:
            raise self.error
        return {**inputs, **self.result}


def client_for(graph, balance=lambda: 4.5):
    return TestClient(create_app(graph_factory=lambda: graph, balance=balance))


def test_ask_returns_answer_status_and_sources():
    graph = FakeGraph({
        "answer": "The AMF handles registration.",
        "termination_reason": "answered",
        "chunks": [
            {"spec_id": "23.501", "version": "17.11.0", "clause_id": "6.2.1", "clause_title": "AMF",
             "chunk_type": "text", "content": "x" * 5000, "cross_score": 3.1},
            {"spec_id": "24.501", "clause_id": "9.11.3.4", "chunk_type": "table",
             "content": [["IEI", "Name"], ["77", "5GS mobile identity"]]},
        ],
    })
    with client_for(graph) as client:
        r = client.post("/api/ask", json={"question": "  What is the AMF?  "})
    assert r.status_code == 200
    body = r.json()
    assert graph.queries == ["What is the AMF?"]
    assert body["answer"] == "The AMF handles registration."
    assert body["status"] == "answered"
    assert body["cached"] is False
    assert body["sources"][0]["clause_title"] == "AMF"
    assert len(body["sources"][0]["excerpt"]) == 600
    assert "cross_score" not in body["sources"][0]
    assert body["sources"][1]["excerpt"] == "IEI | Name\n77 | 5GS mobile identity"


def test_cache_hit_is_reported():
    graph = FakeGraph({"answer": "a", "termination_reason": "answered", "cache_hit": "exact", "chunks": []})
    with client_for(graph) as client:
        assert client.post("/api/ask", json={"question": "q"}).json()["cached"] is True


@pytest.mark.parametrize("question, code", [("   ", "empty_question"), ("x" * 501, "question_too_long")])
def test_rejects_bad_questions_without_running_the_graph(question, code):
    graph = FakeGraph()
    with client_for(graph) as client:
        r = client.post("/api/ask", json={"question": question})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == code
    assert graph.queries == []


def _status_error(status):
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return openai.APIStatusError("err", response=httpx.Response(status, request=request), body=None)


def test_out_of_credit_says_budget_exhausted():
    with client_for(FakeGraph(error=_status_error(402))) as client:
        r = client.post("/api/ask", json={"question": "What is the AMF?"})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "budget_exhausted"


def test_other_llm_errors_are_502():
    with client_for(FakeGraph(error=_status_error(500))) as client:
        r = client.post("/api/ask", json={"question": "What is the AMF?"})
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "llm_error"


def test_unexpected_errors_are_500_without_details():
    with client_for(FakeGraph(error=RuntimeError("qdrant down at 10.0.0.1"))) as client:
        r = client.post("/api/ask", json={"question": "What is the AMF?"})
    assert r.status_code == 500
    assert "10.0.0.1" not in r.text


def test_health_reports_startup_time():
    with client_for(FakeGraph()) as client:
        body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["startup_s"] is not None


def test_quota_reports_budget_and_caches_it():
    calls = []

    def balance():
        calls.append(1)
        return 0.0

    with client_for(FakeGraph(), balance=balance) as client:
        first = client.get("/api/quota").json()
        client.get("/api/quota")
    assert first == {"budget_remaining_usd": 0.0, "budget_exhausted": True}
    assert len(calls) == 1


def test_quota_unknown_budget_is_not_exhausted():
    with client_for(FakeGraph(), balance=lambda: None) as client:
        assert client.get("/api/quota").json()["budget_exhausted"] is False
