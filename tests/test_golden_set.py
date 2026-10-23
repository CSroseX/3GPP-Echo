import glob
import json
import os

from src.eval.metrics import is_prefix_match

GOLDEN_SET_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "eval", "golden", "golden_set.v1.json"
)

CHUNK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chunks")

REQUIRED_FIELDS = {
    "id", "question", "type", "expected_behavior",
    "gold_clauses", "retrieval_scored", "corpus_answerable",
    "borderline", "notes",
}

VALID_TYPES = {"normal", "adversarial", "out_of_scope"}


def _load_golden_set():
    with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_clause_ids_by_spec():
    """Map spec_id -> set of clause_ids present as real chunks."""
    clause_ids_by_spec = {}
    for path in glob.glob(os.path.join(CHUNK_DIR, "*_chunks.json")):
        with open(path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        for chunk in chunks:
            clause_ids_by_spec.setdefault(chunk["spec_id"], set()).add(chunk["clause_id"])
    return clause_ids_by_spec


def _gold_clause_resolves(spec_id, clause_id, clause_ids_by_spec):
    """A gold clause resolves if it (or a descendant of it) exists as a
    real chunk for that spec — exact match or prefix-credit match."""
    candidates = clause_ids_by_spec.get(spec_id, set())
    return any(is_prefix_match(clause_id, candidate) for candidate in candidates)


class TestGoldenSetStructure:
    def test_file_exists(self):
        assert os.path.exists(GOLDEN_SET_PATH)

    def test_has_18_records(self):
        gs = _load_golden_set()
        assert len(gs) == 18

    def test_stable_ids(self):
        gs = _load_golden_set()
        ids = [r["id"] for r in gs]
        assert ids == list(range(1, 19))

    def test_required_fields_present(self):
        gs = _load_golden_set()
        for r in gs:
            missing = REQUIRED_FIELDS - set(r.keys())
            assert not missing, f"Q{r.get('id', '?')} missing fields: {missing}"

    def test_valid_types(self):
        gs = _load_golden_set()
        for r in gs:
            assert r["type"] in VALID_TYPES, f"Q{r['id']} has invalid type: {r['type']}"

    def test_type_counts(self):
        gs = _load_golden_set()
        counts = {}
        for r in gs:
            counts[r["type"]] = counts.get(r["type"], 0) + 1
        assert counts["normal"] == 6
        assert counts["adversarial"] == 6
        assert counts["out_of_scope"] == 6


class TestGoldenSetContent:
    def test_q15_is_borderline(self):
        gs = _load_golden_set()
        q15 = [r for r in gs if r["id"] == 15][0]
        assert q15["borderline"] is True
        assert "TCP" in q15["question"]

    def test_non_borderline_default(self):
        gs = _load_golden_set()
        non_borderline = [r for r in gs if r["id"] != 15]
        for r in non_borderline:
            assert r["borderline"] is False, f"Q{r['id']} unexpectedly borderline"

    def test_normal_questions_have_gold_clauses(self):
        gs = _load_golden_set()
        for r in gs:
            if r["type"] == "normal":
                assert len(r["gold_clauses"]) > 0, f"Q{r['id']} (normal) has no gold_clauses"

    def test_normal_questions_retrieval_scored(self):
        gs = _load_golden_set()
        for r in gs:
            if r["type"] == "normal":
                assert r["retrieval_scored"] is True, f"Q{r['id']} (normal) not retrieval_scored"

    def test_gold_clause_structure(self):
        gs = _load_golden_set()
        for r in gs:
            for gc in r["gold_clauses"]:
                assert "spec_id" in gc, f"Q{r['id']} gold_clause missing spec_id"
                assert "clause_id" in gc, f"Q{r['id']} gold_clause missing clause_id"

    def test_out_of_scope_no_gold_clauses(self):
        gs = _load_golden_set()
        for r in gs:
            if r["type"] == "out_of_scope":
                assert len(r["gold_clauses"]) == 0, f"Q{r['id']} (out_of_scope) has gold_clauses"

    def test_adversarial_not_retrieval_scored(self):
        gs = _load_golden_set()
        for r in gs:
            if r["type"] == "adversarial":
                assert r["retrieval_scored"] is False, f"Q{r['id']} (adversarial) is retrieval_scored"

    def test_questions_match_eval_set(self):
        eval_set_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "eval", "eval_set.json"
        )
        with open(eval_set_path, "r", encoding="utf-8") as f:
            eval_set = json.load(f)

        gs = _load_golden_set()
        eval_questions = [e["question"] for e in eval_set]
        golden_questions = [r["question"] for r in gs]
        assert eval_questions == golden_questions

    def test_baseline_frozen(self):
        """eval/baseline/ must not be modified — the golden set is separate."""
        baseline_gold_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "eval", "baseline", "gold.json"
        )
        assert os.path.exists(baseline_gold_path), "eval/baseline/gold.json must still exist"


class TestGoldenSetResolvesAgainstCorpus:
    """Contract test: every gold_clauses entry must resolve to at least one
    real chunk, exact or descendant. This would have caught the two corpus
    gaps (24.501/5.1.3.2, 23.501/5.15.2) on day one instead of silently
    scoring correct retrievals as misses."""

    def test_all_gold_clauses_resolve_to_a_chunk(self):
        gs = _load_golden_set()
        clause_ids_by_spec = _load_clause_ids_by_spec()
        unresolved = []
        for r in gs:
            for gc in r["gold_clauses"]:
                if not _gold_clause_resolves(gc["spec_id"], gc["clause_id"], clause_ids_by_spec):
                    unresolved.append((r["id"], gc["spec_id"], gc["clause_id"]))
        assert not unresolved, f"Gold clauses with no matching chunk (exact or descendant): {unresolved}"

    def test_known_corpus_gap_cases_resolve_via_descendant(self):
        """Regression guard: these two specific gold clauses only exist as
        descendants, not as exact chunks — assert the contract test still
        credits them rather than silently passing for the wrong reason."""
        clause_ids_by_spec = _load_clause_ids_by_spec()
        assert "5.1.3.2" not in clause_ids_by_spec.get("24.501", set())
        assert _gold_clause_resolves("24.501", "5.1.3.2", clause_ids_by_spec)

        assert "5.15.2" not in clause_ids_by_spec.get("23.501", set())
        assert _gold_clause_resolves("23.501", "5.15.2", clause_ids_by_spec)

    def test_fails_on_a_deliberately_bad_gold_pair(self):
        """A gold clause with no corresponding chunk, anywhere, must be
        flagged — proving the contract test isn't vacuously true."""
        clause_ids_by_spec = _load_clause_ids_by_spec()
        assert not _gold_clause_resolves("23.501", "99.99.99", clause_ids_by_spec)
        assert not _gold_clause_resolves("23.501", "6.2.1.999", clause_ids_by_spec)


GOLDEN_SET_V2_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "eval", "golden", "golden_set.v2.json"
)

V2_CATEGORY_COUNTS = {
    ("normal", "5G"): 13,
    ("normal", "4G"): 8,
    ("trap", "mixed"): 8,
    ("off_topic_obvious", None): 5,
    ("off_topic_telecom", None): 3,
    ("off_topic_3gpp_not_indexed", None): 3,
}


def _load_golden_set_v2():
    with open(GOLDEN_SET_V2_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _gold_text(record, chunks):
    """Whitespace-normalised text of every chunk under the record's gold clauses."""
    parts = []
    for chunk in chunks:
        for gc in record["gold_clauses"]:
            if chunk["spec_id"] == gc["spec_id"] and is_prefix_match(gc["clause_id"], chunk["clause_id"]):
                content = chunk["content"]
                parts.append(content if isinstance(content, str) else json.dumps(content))
    return " ".join(" ".join(parts).split())


class TestGoldenSetV2:
    def test_40_records_with_stable_ids(self):
        assert [r["id"] for r in _load_golden_set_v2()] == list(range(1, 41))

    def test_required_fields_and_types(self):
        for r in _load_golden_set_v2():
            missing = (REQUIRED_FIELDS | {"answer_quotes", "generation", "category", "origin"}) - set(r)
            assert not missing, f"Q{r['id']} missing fields: {missing}"
            assert r["type"] in VALID_TYPES

    def test_category_mix(self):
        counts = {}
        for r in _load_golden_set_v2():
            key = (r["category"], r["generation"])
            counts[key] = counts.get(key, 0) + 1
        assert counts == V2_CATEGORY_COUNTS

    def test_v1_questions_unchanged(self):
        v1 = {r["id"]: r["question"] for r in _load_golden_set()}
        v2 = {r["id"]: r["question"] for r in _load_golden_set_v2() if r["origin"] == "v1"}
        assert v2 == v1

    def test_scored_questions_have_gold_and_quotes(self):
        for r in _load_golden_set_v2():
            assert r["retrieval_scored"] == (r["category"] in {"normal", "trap"}), f"Q{r['id']}"
            if r["retrieval_scored"]:
                assert r["gold_clauses"] and r["answer_quotes"], f"Q{r['id']} lacks gold or quotes"

    def test_all_gold_clauses_resolve_to_a_chunk(self):
        clause_ids_by_spec = _load_clause_ids_by_spec()
        unresolved = [
            (r["id"], gc["spec_id"], gc["clause_id"])
            for r in _load_golden_set_v2()
            for gc in r["gold_clauses"]
            if not _gold_clause_resolves(gc["spec_id"], gc["clause_id"], clause_ids_by_spec)
        ]
        assert not unresolved, f"Gold clauses with no matching chunk: {unresolved}"

    def test_answer_quotes_appear_verbatim_in_gold_chunks(self):
        """Each quoted fragment (split on the ellipsis) must occur in the gold
        clauses' chunk text, so a re-chunk that loses answer text fails loudly."""
        chunks = []
        for path in glob.glob(os.path.join(CHUNK_DIR, "*_chunks.json")):
            with open(path, "r", encoding="utf-8") as f:
                chunks.extend(json.load(f))
        missing = []
        for r in _load_golden_set_v2():
            text = _gold_text(r, chunks)
            for quote in r["answer_quotes"]:
                body = quote[quote.index('"') + 1: quote.rindex('"')]
                for fragment in (" ".join(f.split()) for f in body.split("…")):
                    if len(fragment) >= 12 and fragment not in text:
                        missing.append((r["id"], fragment[:80]))
        assert not missing, f"Answer quotes not found in gold chunks: {missing}"
