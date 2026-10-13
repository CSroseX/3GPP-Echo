from types import SimpleNamespace

import openai
import pytest

from src.obs import tracing


@pytest.fixture(autouse=True)
def no_langfuse(monkeypatch):
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    tracing.reset_usage()
    yield
    tracing.reset_usage()


def make_fake_client(usage):
    def create(**kwargs):
        return SimpleNamespace(usage=usage, choices=[])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


class TestFactoryWithoutLangfuse:
    def test_tracing_disabled_when_host_unset(self):
        assert tracing.tracing_enabled() is False

    def test_returns_plain_openai_client(self):
        client = tracing.make_llm_client(api_key="k", base_url="http://localhost:1/v1")
        assert isinstance(client, openai.OpenAI)

    def test_observe_bare_passes_through(self):
        def node(state):
            return {"seen": state["x"]}

        wrapped = tracing.observe(node)
        assert wrapped({"x": 1}) == {"seen": 1}
        assert wrapped.__name__ == "node"

    def test_observe_with_args_passes_through(self):
        def node(state):
            return {"seen": state["x"]}

        assert tracing.observe(name="generate")(node)({"x": 2}) == {"seen": 2}

    def test_observe_switches_to_langfuse_once_enabled_at_call_time(self, monkeypatch):
        # Decorated while tracing is off (as at import, before .env loads) ...
        calls = []

        def fake_lf_observe(fn, **kwargs):
            calls.append(kwargs)
            return lambda *a, **k: ("traced", fn(*a, **k))

        @tracing.observe(name="generate")
        def node(state):
            return state["x"]

        assert node({"x": 3}) == 3
        # ... then enabled: the next call goes through langfuse.observe.
        monkeypatch.setattr(tracing, "tracing_enabled", lambda: True)
        monkeypatch.setattr("langfuse.observe", fake_lf_observe)
        assert node({"x": 4}) == ("traced", 4)
        assert node({"x": 5}) == ("traced", 5)
        assert calls == [{"name": "generate"}]

    def test_update_trace_attributes_is_noop(self):
        tracing.update_trace_attributes(termination_reason="verified", attempt=1)


class TestUsageRecording:
    def test_usage_recorded_per_call(self):
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        client = tracing._wrap_usage(make_fake_client(usage))

        cursor = tracing.usage_snapshot()
        client.chat.completions.create(model="m", messages=[])
        client.chat.completions.create(model="m", messages=[])

        records = tracing.usage_since(cursor)
        assert len(records) == 2
        assert records[0] == {"model": "m", "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}

    def test_cursor_excludes_earlier_calls(self):
        usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
        client = tracing._wrap_usage(make_fake_client(usage))
        client.chat.completions.create(model="m", messages=[])

        cursor = tracing.usage_snapshot()
        client.chat.completions.create(model="m", messages=[])
        assert len(tracing.usage_since(cursor)) == 1

    def test_response_without_usage_is_skipped(self):
        client = tracing._wrap_usage(make_fake_client(None))
        client.chat.completions.create(model="m", messages=[])
        assert tracing.usage_since(0) == []

    def test_live_client_create_is_wrapped(self):
        client = tracing.make_llm_client(api_key="k", base_url="http://localhost:1/v1")
        assert client.chat.completions.create.__wrapped__ is not None
