"""generate_node: the single LLM call, its status label and the identifier check."""

import types

import pytest

from src.generation import nodes as gen_nodes


def make_chunks():
    return [{"spec_id": "24.501", "clause_id": "5.5.1.2.2",
             "content": "The UE sends a REGISTRATION REQUEST message to the AMF, starting timer T3510."}]


def make_response(content):
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))])


@pytest.fixture
def reply(monkeypatch):
    def set_reply(*contents):
        calls = []
        replies = list(contents)

        def create(*a, **k):
            calls.append(k)
            return make_response(replies.pop(0) if len(replies) > 1 else replies[0])

        monkeypatch.setattr(gen_nodes.client.chat.completions, "create", create)
        return calls
    return set_reply


def run(question="Which timer does the UE start?", chunks=None):
    return gen_nodes.generate_node({"query": question, "chunks": make_chunks() if chunks is None else chunks})


class TestStatusLabel:
    def test_answered(self, reply):
        reply("The UE starts timer T3510 when it sends a REGISTRATION REQUEST.\nSTATUS: answered")
        result = run()
        assert result["termination_reason"] == "answered"
        assert result["answer"] == "The UE starts timer T3510 when it sends a REGISTRATION REQUEST."

    def test_missing_status_line_is_partial(self, reply):
        reply("The UE starts timer T3510.")
        assert run()["termination_reason"] == "partial"

    def test_not_covered(self, reply):
        reply("This isn't defined in the 5G specifications.\nSTATUS: not_covered")
        assert run()["termination_reason"] == "not_covered"


class TestIdentifierCheck:
    def test_answered_with_identifier_missing_from_sources_is_downgraded(self, reply):
        reply("The UE starts timer T3410.\nSTATUS: answered")
        result = run()
        assert result["termination_reason"] == "partial"
        assert result["unsupported_identifiers"] == ["T3410"]

    def test_partial_stays_partial_and_records_identifiers(self, reply):
        reply("Probably T3410.\nSTATUS: partial")
        result = run()
        assert result["termination_reason"] == "partial"
        assert result["unsupported_identifiers"] == ["T3410"]


class TestNoAnswer:
    def test_no_chunks_is_not_covered_without_an_llm_call(self, reply):
        calls = reply("should not be used")
        result = run(chunks=[])
        assert result["termination_reason"] == "not_covered"
        assert calls == []

    def test_empty_reply_is_no_answer(self, reply):
        reply(None)
        result = run()
        assert result["termination_reason"] == "no_answer"
        assert result["answer"] == gen_nodes.core.EMPTY_ANSWER

    def test_one_call_per_question(self, reply):
        calls = reply("The UE starts timer T3510.\nSTATUS: answered")
        run()
        assert len(calls) == 1


class TestPrompt:
    def test_prompt_asks_for_the_status_line(self, reply):
        calls = reply("x\nSTATUS: answered")
        run()
        system = calls[0]["messages"][0]["content"]
        assert "STATUS: answered" in system and "STATUS: not_covered" in system

    def test_banned_phrase_triggers_one_rephrase(self, reply):
        calls = reply("The provided text says T3510.\nSTATUS: answered",
                      "The UE starts timer T3510.\nSTATUS: answered")
        result = run()
        assert len(calls) == 2
        assert result["answer"] == "The UE starts timer T3510."
