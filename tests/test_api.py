"""Public API (src/api/main.py), driven with a fake graph: no models, Qdrant or LLM."""

import json

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.quota import Quota, ip_bucket, issue_token, verify_token


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

    def stream(self, inputs, stream_mode="updates"):
        """Yield the result as per-node updates, like LangGraph's updates mode."""
        self.queries.append(inputs["query"])
        for node, update in self.result.get("_steps", []):
            yield {node: update}
        if self.error:
            raise self.error


class FakeStore:
    """In-memory stand-in for Upstash: counters by key."""

    def __init__(self, fail=False):
        self.counts = {}
        self.fail = fail

    def get_many(self, keys):
        if self.fail:
            raise ConnectionError("redis down")
        return [self.counts.get(k, 0) for k in keys]

    def incr_many(self, keys, ttl_seconds):
        if self.fail:
            raise ConnectionError("redis down")
        for k in keys:
            self.counts[k] = self.counts.get(k, 0) + 1
        return [self.counts[k] for k in keys]


def no_quota():
    return Quota(None, "test-secret", per_visitor=5, per_ip=15)


def client_for(graph, balance=lambda: 4.5, quota=no_quota):
    """No network: quota off unless a test passes one (never reads .env's Upstash)."""
    return TestClient(create_app(graph_factory=lambda: graph, balance=balance, quota_factory=quota))


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
    assert first["budget_remaining_usd"] == 0.0 and first["budget_exhausted"] is True
    assert len(calls) == 1


def test_quota_unknown_budget_is_not_exhausted():
    with client_for(FakeGraph(), balance=lambda: None) as client:
        assert client.get("/api/quota").json()["budget_exhausted"] is False


def parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_stream_sends_node_facts_then_the_answer():
    chunks = [{"spec_id": "23.501", "clause_id": "6.2.1", "clause_title": "AMF", "content": "AMF text"}]
    graph = FakeGraph({"_steps": [
        ("cache_lookup", {"cache_hit": None}),
        ("triage", {"triage_decision": "in_domain", "triage_tier": "lexical",
                    "triage_signals": {"acronyms": ["AMF"], "spec_ids": []}}),
        ("retrieve", {"chunks": chunks}),
        ("generate", {"answer": "The AMF ...", "termination_reason": "answered", "unsupported_identifiers": []}),
        ("cache_store", None),
    ]})
    with client_for(graph) as client:
        r = client.post("/api/ask/stream", json={"question": "What is the AMF?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    names = [e for e, _ in events]
    assert names == ["start", "node", "node", "node", "node", "node", "done"]
    nodes = {d["node"]: d for e, d in events if e == "node"}
    assert nodes["triage"]["facts"] == {"decision": "in_domain", "tier": "lexical", "matched": ["AMF"],
                                        "mixed_generation": False}
    assert nodes["retrieve"]["facts"] == {"count": 1, "specs": {"23.501": 1}, "clauses": ["23.501 §6.2.1"]}
    assert nodes["generate"]["facts"]["status"] == "answered"
    assert all(isinstance(d["ms"], int) for e, d in events if e == "node")
    done = events[-1][1]
    assert done["answer"] == "The AMF ..." and done["status"] == "answered"
    assert done["sources"][0]["clause_title"] == "AMF"


def test_stream_reports_mixed_generation_terms():
    graph = FakeGraph({"_steps": [
        ("triage", {"triage_decision": "in_domain", "triage_tier": "lexical", "mixed_generation": True,
                    "generation_terms": {"4g": ["MME"], "5g": ["UDM"]}, "triage_signals": {}}),
    ]})
    with client_for(graph) as client:
        events = parse_sse(client.post("/api/ask/stream", json={"question": "q"}).text)
    facts = events[1][1]["facts"]
    assert facts["mixed_generation"] is True
    assert facts["terms_4g"] == ["MME"] and facts["terms_5g"] == ["UDM"]


def test_stream_turns_out_of_credit_into_an_error_event():
    graph = FakeGraph({"_steps": [("cache_lookup", {})]}, error=_status_error(402))
    with client_for(graph) as client:
        events = parse_sse(client.post("/api/ask/stream", json={"question": "q"}).text)
    assert [e for e, _ in events] == ["start", "node", "error"]
    assert events[-1][1]["code"] == "budget_exhausted"


def test_stream_rejects_bad_questions_before_streaming():
    graph = FakeGraph()
    with client_for(graph) as client:
        r = client.post("/api/ask/stream", json={"question": "   "})
    assert r.status_code == 422
    assert graph.queries == []


# ── Budget protection ────────────────────────────────────────────────

ANSWERED = {"answer": "a", "termination_reason": "answered", "chunks": [{"spec_id": "23.501", "content": "x"}]}


def quota_with(store, per_visitor=2, per_ip=3):
    return lambda: Quota(store, "test-secret", per_visitor=per_visitor, per_ip=per_ip)


def test_tokens_are_signed():
    token = issue_token("s")
    assert verify_token(token, "s")
    assert verify_token(token, "other") is None
    assert verify_token(token[:-1] + ("0" if token[-1] != "0" else "1"), "s") is None
    assert verify_token(None, "s") is None and verify_token("garbage", "s") is None


def test_ipv6_is_bucketed_by_64():
    assert ip_bucket("2001:db8:1:2:aaaa::1") == ip_bucket("2001:db8:1:2:bbbb::9") == "2001:db8:1:2::/64"
    assert ip_bucket("203.0.113.7") == "203.0.113.7"
    assert ip_bucket(None) == ip_bucket("nonsense") == "unknown"


def test_quota_issues_a_token_and_reports_questions_left():
    store = FakeStore()
    with client_for(FakeGraph(), quota=quota_with(store)) as client:
        body = client.get("/api/quota").json()
        assert body["questions_left"] == 2 and body["questions_per_day"] == 2
        token = body["visitor_token"]
        again = client.get("/api/quota", headers={"X-Visitor-Token": token}).json()
        assert again["visitor_token"] == token  # a genuine token is kept
        forged = client.get("/api/quota", headers={"X-Visitor-Token": "abc.def"}).json()
        assert forged["visitor_token"] != "abc.def"


def test_llm_answers_are_charged_until_the_limit():
    store = FakeStore()
    with client_for(FakeGraph(ANSWERED), quota=quota_with(store, per_visitor=2)) as client:
        token = client.get("/api/quota").json()["visitor_token"]
        h = {"X-Visitor-Token": token}
        assert client.post("/api/ask", json={"question": "q"}, headers=h).json()["questions_left"] == 1
        assert client.post("/api/ask", json={"question": "q"}, headers=h).json()["questions_left"] == 0
        r = client.post("/api/ask", json={"question": "q"}, headers=h)
        assert r.status_code == 429 and r.json()["detail"]["code"] == "quota_exhausted"
        s = client.post("/api/ask/stream", json={"question": "q"}, headers=h)
        assert s.status_code == 429


def test_refusals_and_cache_hits_are_free():
    store = FakeStore()
    refused = {"answer": "no", "termination_reason": "out_of_domain", "chunks": []}
    cached = {**ANSWERED, "cache_hit": "exact"}
    for result in (refused, cached):
        with client_for(FakeGraph(result), quota=quota_with(store, per_visitor=1)) as client:
            token = client.get("/api/quota").json()["visitor_token"]
            for _ in range(3):
                r = client.post("/api/ask", json={"question": "q"}, headers={"X-Visitor-Token": token})
                assert r.status_code == 200 and r.json()["questions_left"] == 1
    assert store.counts == {}


def test_new_tokens_on_one_ip_stop_at_the_ip_limit():
    store = FakeStore()
    with client_for(FakeGraph(ANSWERED), quota=quota_with(store, per_visitor=2, per_ip=3)) as client:
        codes = []
        for _ in range(4):  # a fresh token each time, same IP
            token = client.get("/api/quota").json()["visitor_token"]
            codes.append(client.post("/api/ask", json={"question": "q"}, headers={"X-Visitor-Token": token}).status_code)
    assert codes == [200, 200, 200, 429]


def test_no_token_gets_the_per_visitor_limit_on_its_ip():
    store = FakeStore()
    with client_for(FakeGraph(ANSWERED), quota=quota_with(store, per_visitor=2, per_ip=10)) as client:
        codes = [client.post("/api/ask", json={"question": "q"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_stream_done_event_carries_questions_left():
    store = FakeStore()
    graph = FakeGraph({"_steps": [("retrieve", {"chunks": [{"spec_id": "23.501", "content": "x"}]}),
                                  ("generate", {"answer": "a", "termination_reason": "answered"})]})
    with client_for(graph, quota=quota_with(store, per_visitor=2)) as client:
        token = client.get("/api/quota").json()["visitor_token"]
        events = parse_sse(client.post("/api/ask/stream", json={"question": "q"},
                                       headers={"X-Visitor-Token": token}).text)
    assert events[-1][0] == "done" and events[-1][1]["questions_left"] == 1


def test_redis_outage_fails_open():
    with client_for(FakeGraph(ANSWERED), quota=quota_with(FakeStore(fail=True))) as client:
        r = client.post("/api/ask", json={"question": "q"})
    assert r.status_code == 200 and r.json()["questions_left"] is None
