import json

import pytest

from src.eval.runner import (
    GoldenSetDriftError,
    ResultsFileCorruptError,
    atomic_write_json,
    golden_set_hash,
    load_existing_results,
)


def make_golden_set():
    return [
        {"id": 1, "question": "Q1?", "type": "normal"},
        {"id": 2, "question": "Q2?", "type": "adversarial"},
        {"id": 3, "question": "Q3?", "type": "out_of_scope"},
    ]


class TestGoldenSetHash:
    def test_same_content_same_hash(self):
        gs = make_golden_set()
        assert golden_set_hash(gs) == golden_set_hash(list(gs))

    def test_different_content_different_hash(self):
        gs1 = make_golden_set()
        gs2 = make_golden_set()
        gs2[0]["question"] = "Changed?"
        assert golden_set_hash(gs1) != golden_set_hash(gs2)

    def test_reordering_does_not_change_hash_content_but_id_keying_handles_it(self):
        # sort_keys in json.dumps sorts dict keys, not list order, so a
        # reordered list IS a different hash (list order is preserved).
        gs1 = make_golden_set()
        gs2 = list(reversed(make_golden_set()))
        assert golden_set_hash(gs1) != golden_set_hash(gs2)


class TestLoadExistingResultsNoFile:
    def test_missing_file_returns_empty_dict(self, tmp_path):
        path = tmp_path / "results.json"
        result = load_existing_results(path, expected_hash="anything")
        assert result == {}


class TestLoadExistingResultsCorruptFile:
    def test_malformed_json_raises_instead_of_silently_discarding(self, tmp_path):
        path = tmp_path / "results.json"
        path.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ResultsFileCorruptError):
            load_existing_results(path, expected_hash="anything")

    def test_corrupt_file_is_left_on_disk_after_raising(self, tmp_path):
        path = tmp_path / "results.json"
        path.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ResultsFileCorruptError):
            load_existing_results(path, expected_hash="anything")
        # The old bug silently wiped the file on the next write; this
        # function must not touch the file at all when it can't parse it.
        assert path.read_text(encoding="utf-8") == "{not valid json"


class TestLoadExistingResultsDriftDetection:
    def test_matching_hash_loads_results_keyed_by_id(self, tmp_path):
        gs = make_golden_set()
        h = golden_set_hash(gs)
        path = tmp_path / "results.json"
        path.write_text(json.dumps({
            "golden_set_hash": h,
            "results": [{"id": 1, "question": "Q1?", "answer": "x"}],
        }), encoding="utf-8")

        loaded = load_existing_results(path, expected_hash=h)
        assert loaded == {1: {"id": 1, "question": "Q1?", "answer": "x"}}

    def test_mismatched_hash_raises_drift_error(self, tmp_path):
        gs = make_golden_set()
        h = golden_set_hash(gs)
        path = tmp_path / "results.json"
        path.write_text(json.dumps({
            "golden_set_hash": "some-stale-hash",
            "results": [{"id": 1, "question": "Q1?", "answer": "x"}],
        }), encoding="utf-8")

        with pytest.raises(GoldenSetDriftError):
            load_existing_results(path, expected_hash=h)

    def test_missing_hash_field_is_tolerated_for_backward_compat(self, tmp_path):
        """A results file with no golden_set_hash (e.g. hand-written, or
        from before this field existed) should load, not drift-error."""
        path = tmp_path / "results.json"
        path.write_text(json.dumps({
            "results": [{"id": 1, "question": "Q1?", "answer": "x"}],
        }), encoding="utf-8")
        loaded = load_existing_results(path, expected_hash="whatever")
        assert loaded == {1: {"id": 1, "question": "Q1?", "answer": "x"}}


class TestAtomicWriteJson:
    def test_writes_valid_json(self, tmp_path):
        path = tmp_path / "out.json"
        atomic_write_json(path, {"a": 1})
        assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}

    def test_no_leftover_temp_file(self, tmp_path):
        path = tmp_path / "out.json"
        atomic_write_json(path, {"a": 1})
        assert not (tmp_path / "out.json.tmp").exists()

    def test_overwrites_existing_file_completely(self, tmp_path):
        path = tmp_path / "out.json"
        atomic_write_json(path, {"a": 1, "b": 2})
        atomic_write_json(path, {"c": 3})
        assert json.loads(path.read_text(encoding="utf-8")) == {"c": 3}


class FakeApp:
    """Stands in for the compiled graph: yields one {node: update} per node
    and records token usage the way the traced client would."""

    def __init__(self, steps):
        self.steps = steps

    def stream(self, inputs):
        from types import SimpleNamespace

        from src.obs import tracing

        for node_name, update, tokens in self.steps:
            if tokens:
                usage = SimpleNamespace(prompt_tokens=tokens[0], completion_tokens=tokens[1],
                                        total_tokens=sum(tokens))
                tracing._record_usage(SimpleNamespace(usage=usage), "fake-model")
            yield {node_name: update}


class TestRunOneQuestionRecording:
    def test_records_node_path_tokens_and_termination(self, tmp_path):
        from src.eval.runner import run_one_question
        from src.obs.metrics import RunRecorder

        app = FakeApp([
            ("retrieve", {"chunks": [{"spec_id": "23.501", "clause_id": "6.2.1"}]}, None),
            ("generate", {"answer": "The AMF ...", "termination_reason": "answered"}, (100, 20)),
            ("cache_store", {}, None),
        ])
        recorder = RunRecorder(run_id="test", output_dir=tmp_path)
        recorder.start_run(model_name="fake-model")

        result = run_one_question(app, {"id": 1, "question": "Q1?", "type": "normal"}, recorder=recorder)
        recorder.end_run()

        assert result["termination_reason"] == "answered"
        assert result["sources"] == [{"spec_id": "23.501", "clause_id": "6.2.1"}]

        record = json.loads((tmp_path / "per_question.jsonl").read_text(encoding="utf-8").strip())
        assert record["node_path"] == ["retrieve", "generate", "cache_store"]
        assert [n["tokens_in"] for n in record["nodes"]] == [0, 100, 0]
        assert [n["llm_calls"] for n in record["nodes"]] == [0, 1, 0]
        assert record["total_tokens_in"] == 100
        assert record["total_tokens_out"] == 20
        assert record["termination_reason"] == "answered"

        summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        assert summary["total_tokens"] == 120
        assert summary["termination_reasons"] == {"answered": 1}

    def test_records_how_each_decision_node_decided(self, tmp_path):
        from src.eval.runner import run_one_question
        from src.obs.metrics import RunRecorder

        app = FakeApp([
            ("cache_lookup", None, None),
            ("triage", {"triage_decision": "in_domain", "triage_tier": "lexical", "triage_score": None,
                        "mixed_generation": True, "retrieval_queries": ["MME part TS 24.301", "UDM part"]}, None),
            ("retrieve", {"chunks": [{"spec_id": "23.501", "clause_id": "6.2.1"}]}, None),
            ("generate", {"answer": "The AMF ...", "termination_reason": "partial",
                          "unsupported_identifiers": ["T3410"]}, (100, 20)),
        ])
        recorder = RunRecorder(run_id="test", output_dir=tmp_path)
        recorder.start_run(model_name="fake-model")
        result = run_one_question(app, {"id": 1, "question": "Q1?", "type": "normal"}, recorder=recorder)
        recorder.end_run()

        expected = {"triage_decision": "in_domain", "triage_tier": "lexical", "mixed_generation": True,
                    "retrieval_queries": ["MME part TS 24.301", "UDM part"], "unsupported_identifiers": ["T3410"]}
        assert result["decisions"] == expected  # triage_score None is left out
        record = json.loads((tmp_path / "per_question.jsonl").read_text(encoding="utf-8").strip())
        assert record["decisions"] == expected

    def test_without_recorder_still_returns_result(self):
        from src.eval.runner import run_one_question

        app = FakeApp([("refuse", {"termination_reason": "out_of_domain", "chunks": []}, None)])
        result = run_one_question(app, {"id": 2, "question": "Q2?", "type": "out_of_scope"})
        assert result["termination_reason"] == "out_of_domain"
        assert result["sources"] == []


class TestRunMetadata:
    def test_records_code_version_and_settings_without_secrets(self, monkeypatch):
        from src.config import Settings
        from src.eval.runner import run_metadata

        monkeypatch.setenv("GENERATE_MAX_TOKENS", "2000")
        monkeypatch.setenv("OPEN_ROUTER_API_KEY", "sk-secret")
        meta = run_metadata(Settings())

        assert meta["settings"]["generate_max_tokens"] == 2000
        assert "sk-secret" not in json.dumps(meta)
        assert not any("key" in k for k in meta["settings"])
        # Inside the repo, git resolves a 40-character commit id.
        assert meta["git_commit"] is None or len(meta["git_commit"]) == 40


class TestRunCallCap:
    def _setup(self, monkeypatch, tmp_path, steps):
        from src.eval import runner
        from src.obs.metrics import RunRecorder

        monkeypatch.setattr(runner, "Retriever", lambda: None)
        monkeypatch.setattr(runner, "build_graph", lambda retriever: FakeApp(steps))
        monkeypatch.setattr(runner, "RunRecorder", lambda: RunRecorder(run_id="cap", output_dir=tmp_path / "run"))
        golden = tmp_path / "golden.json"
        golden.write_text(json.dumps([{"id": i, "question": f"Q{i}?", "type": "normal"} for i in range(1, 5)]),
                          encoding="utf-8")
        return runner, golden

    def teardown_method(self):
        from src.config import get_settings
        get_settings.cache_clear()

    def test_stops_before_a_question_that_could_pass_the_cap(self, monkeypatch, tmp_path):
        steps = [("generate", {"answer": "a", "termination_reason": "answered"}, (10, 1))]
        runner, golden = self._setup(monkeypatch, tmp_path, steps)
        # 1 call per question, worst case 3: questions start at 0, 1, 2 used calls; 3 + 3 > 5 stops.
        results = runner.run(golden_set_path=golden, results_path=tmp_path / "r.json",
                             sleep_seconds=0, max_llm_calls=5)
        assert [r["id"] for r in results] == [1, 2, 3]

    def test_provider_error_stops_the_run_and_keeps_finished_results(self, monkeypatch, tmp_path):
        class FailingApp(FakeApp):
            def stream(self, inputs):
                if inputs["query"] == "Q2?":
                    raise RuntimeError("402 Payment Required")
                yield from super().stream(inputs)

        from src.eval import runner as runner_module
        steps = [("generate", {"answer": "a", "termination_reason": "answered"}, (10, 1))]
        runner, golden = self._setup(monkeypatch, tmp_path, steps)
        monkeypatch.setattr(runner_module, "build_graph", lambda retriever: FailingApp(steps))
        try:
            runner.run(golden_set_path=golden, results_path=tmp_path / "r.json", sleep_seconds=0, max_llm_calls=40)
        except RuntimeError:
            pass
        saved = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["results"]
        assert [r["id"] for r in saved] == [1]
