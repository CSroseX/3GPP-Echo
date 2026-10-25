import math

import pytest

from src.eval.metrics import (
    cross_spec_coverage,
    is_prefix_match,
    mrr,
    ndcg_at_k,
    normalize_pair,
    recall_at_k,
    score_chunk_grades,
    score_question,
)


def make_result(spec_id, clause_id, score=1.0):
    return {"spec_id": spec_id, "clause_id": clause_id, "score": score}


class TestIsPrefixMatch:
    def test_exact_match(self):
        assert is_prefix_match("5.15.2", "5.15.2") is True

    def test_strict_descendant_matches(self):
        assert is_prefix_match("5.15.2", "5.15.2.1") is True
        assert is_prefix_match("5.15.2", "5.15.2.1.3") is True

    def test_sibling_does_not_match(self):
        assert is_prefix_match("5.15.2", "5.15.3") is False

    def test_unrelated_prefix_does_not_match(self):
        # "5.15.20" is not a descendant of "5.15.2" even though it shares
        # the string prefix "5.15.2" — the dot boundary matters.
        assert is_prefix_match("5.15.2", "5.15.20") is False

    def test_ancestor_of_gold_does_not_match(self):
        # Retrieved clause is a parent of gold, not a child — not credited.
        assert is_prefix_match("5.15.2.1", "5.15.2") is False


class TestNormalizePair:
    def test_normalize(self):
        assert normalize_pair({"spec_id": "23.501", "clause_id": "6.2.1"}) == ("23.501", "6.2.1")


class TestRecallAtK:
    def test_strict_exact_hit(self):
        results = [make_result("23.501", "6.2.1")]
        assert recall_at_k(results, [("23.501", "6.2.1")], k=5, strict=True) == 1.0

    def test_strict_misses_descendant(self):
        # The real-world bug: gold is an ancestor clause that doesn't exist
        # as a chunk; only its descendant was indexed and retrieved.
        results = [make_result("23.501", "5.15.2.1")]
        assert recall_at_k(results, [("23.501", "5.15.2")], k=5, strict=True) == 0.0

    def test_prefix_credit_covers_descendant(self):
        results = [make_result("23.501", "5.15.2.1")]
        assert recall_at_k(results, [("23.501", "5.15.2")], k=5, strict=False) == 1.0

    def test_multi_gold_partial_credit(self):
        results = [make_result("24.501", "6.4.1.2")]
        gold = [("24.501", "6.4.1.2"), ("24.501", "6.4.1.1")]
        assert recall_at_k(results, gold, k=5, strict=True) == 0.5

    def test_no_gold_pairs_returns_zero(self):
        assert recall_at_k([make_result("23.501", "6.2.1")], [], k=5, strict=True) == 0.0

    def test_respects_k_cutoff(self):
        results = [make_result("23.501", "1.1") for _ in range(10)]
        results.append(make_result("23.501", "6.2.1"))
        assert recall_at_k(results, [("23.501", "6.2.1")], k=5, strict=True) == 0.0
        assert recall_at_k(results, [("23.501", "6.2.1")], k=20, strict=True) == 1.0

    def test_wrong_spec_does_not_match(self):
        results = [make_result("24.501", "6.2.1")]
        assert recall_at_k(results, [("23.501", "6.2.1")], k=5, strict=True) == 0.0


class TestMRR:
    def test_first_rank_hit(self):
        results = [make_result("23.501", "6.2.1")]
        assert mrr(results, [("23.501", "6.2.1")], strict=True) == 1.0

    def test_third_rank_hit(self):
        results = [make_result("23.501", "1.1"), make_result("23.501", "1.2"), make_result("23.501", "6.2.1")]
        assert mrr(results, [("23.501", "6.2.1")], strict=True) == pytest.approx(1 / 3)

    def test_no_hit_is_zero(self):
        results = [make_result("23.501", "1.1")]
        assert mrr(results, [("23.501", "6.2.1")], strict=True) == 0.0

    def test_prefix_credit_improves_rank(self):
        results = [make_result("23.501", "1.1"), make_result("23.501", "5.15.2.1")]
        assert mrr(results, [("23.501", "5.15.2")], strict=True) == 0.0
        assert mrr(results, [("23.501", "5.15.2")], strict=False) == 0.5


class TestNdcgAtK:
    def test_perfect_rank_is_one(self):
        results = [make_result("23.501", "6.2.1")]
        assert ndcg_at_k(results, [("23.501", "6.2.1")], k=10, strict=True) == pytest.approx(1.0)

    def test_no_gold_pairs_is_zero(self):
        assert ndcg_at_k([make_result("23.501", "6.2.1")], [], k=10, strict=True) == 0.0

    def test_lower_rank_scores_less_than_one(self):
        results = [make_result("23.501", "1.1"), make_result("23.501", "6.2.1")]
        score = ndcg_at_k(results, [("23.501", "6.2.1")], k=10, strict=True)
        assert 0.0 < score < 1.0

    def test_prefix_credit_scores_higher_than_strict(self):
        results = [make_result("23.501", "5.15.2.1")]
        strict_score = ndcg_at_k(results, [("23.501", "5.15.2")], k=10, strict=True)
        prefix_score = ndcg_at_k(results, [("23.501", "5.15.2")], k=10, strict=False)
        assert strict_score == 0.0
        assert prefix_score == pytest.approx(1.0)

    def test_several_chunks_of_one_gold_clause_never_exceed_one(self):
        # Q2-shaped: two gold clauses, each split over several chunks.
        results = [make_result("24.501", "6.4.1.2"), make_result("24.501", "6.4.1.2"),
                   make_result("24.501", "6.4.1.1"), make_result("24.501", "6.4.1.2")]
        gold = [("24.501", "6.4.1.2"), ("24.501", "6.4.1.1")]
        assert ndcg_at_k(results, gold, k=10, strict=True) <= 1.0

    def test_each_gold_pair_credited_at_first_hit(self):
        # Gold at ranks 1 and 3 (rank 2 is a duplicate chunk of the first).
        results = [make_result("24.501", "6.4.1.2"), make_result("24.501", "6.4.1.2"),
                   make_result("24.501", "6.4.1.1")]
        gold = [("24.501", "6.4.1.2"), ("24.501", "6.4.1.1")]
        expected = (1 + 1 / math.log2(4)) / (1 + 1 / math.log2(3))
        assert ndcg_at_k(results, gold, k=10, strict=True) == pytest.approx(expected)

    def test_prefix_descendants_of_one_gold_count_once(self):
        results = [make_result("23.501", "5.15.2.1"), make_result("23.501", "5.15.2.2")]
        assert ndcg_at_k(results, [("23.501", "5.15.2")], k=10, strict=False) == pytest.approx(1.0)


class TestScoreQuestion:
    def test_reports_both_variants(self):
        results = [make_result("23.501", "5.15.2.1")]
        gold = [{"spec_id": "23.501", "clause_id": "5.15.2"}]
        scores = score_question(results, gold)
        assert "strict" in scores and "prefix_credit" in scores
        assert scores["strict"]["recall_at_5"] == 0.0
        assert scores["prefix_credit"]["recall_at_5"] == 1.0

    def test_known_corpus_gap_cases(self):
        """Regression test for the two documented corpus gaps: gold clauses
        24.501/5.1.3.2 and 23.501/5.15.2 exist only as descendant chunks."""
        results = [make_result("24.501", "5.1.3.2.1.1")]
        gold = [{"spec_id": "24.501", "clause_id": "5.1.3.2"}]
        scores = score_question(results, gold)
        assert scores["strict"]["recall_at_5"] == 0.0
        assert scores["prefix_credit"]["recall_at_5"] == 1.0


class TestScoreChunkGrades:
    GRADES = {"ans": 2, "help": 1, "junk": 0}

    def ranked(self, *chunk_ids):
        return [{"chunk_id": cid} for cid in chunk_ids]

    def test_answer_in_top_5(self):
        out = score_chunk_grades(self.ranked("junk", "help", "ans"), self.GRADES)
        assert out["answer_at_5"] == 1
        assert out["answer_at_10"] == 1
        assert out["relevant_at_5"] == 1
        assert out["first_answer_rank"] == 3

    def test_answer_at_rank_6_counts_only_for_top_10(self):
        out = score_chunk_grades(self.ranked("junk", "x1", "x2", "x3", "x4", "ans"), self.GRADES)
        assert out["answer_at_5"] == 0
        assert out["answer_at_10"] == 1
        assert out["first_answer_rank"] == 6

    def test_unjudged_chunks_score_zero_and_are_counted(self):
        out = score_chunk_grades(self.ranked("x1", "x2", "junk"), self.GRADES)
        assert out["answer_at_5"] == 0
        assert out["relevant_at_5"] == 0
        assert out["first_answer_rank"] is None
        assert out["unjudged_in_top_5"] == 2


class TestCrossSpecCoverage:
    GOLD = [{"spec_id": "24.301", "clause_id": "5.5.1"}, {"spec_id": "23.501", "clause_id": "6.2.7"}]

    def test_both_specs_in_top_5(self):
        results = [make_result("24.301", "1"), make_result("23.501", "2")]
        out = cross_spec_coverage(results, self.GOLD)
        assert out == {"specs_covered_at_5": 2, "specs_needed": 2, "all_specs_at_5": 1}

    def test_one_spec_missing(self):
        results = [make_result("24.301", str(i)) for i in range(5)] + [make_result("23.501", "x")]
        out = cross_spec_coverage(results, self.GOLD)
        assert out["specs_covered_at_5"] == 1 and out["all_specs_at_5"] == 0
