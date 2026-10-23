"""Tests for the pooling script's tokenizer and exact-term extraction (no Qdrant, no models)."""

import pytest

pytest.importorskip("qdrant_client")

from src.eval.pool_candidates import exact_terms, grading_rows, stem_tokens  # noqa: E402


def test_stemming_matches_word_forms():
    assert stem_tokens("selection")[0] == stem_tokens("selecting")[0]


def test_joined_terms_kept_whole_and_split():
    tokens = stem_tokens("5G-GUTI and S-NSSAI")
    assert "5g-guti" in tokens and "s-nssai" in tokens
    assert "nssai" in tokens  # a bare "NSSAI" query still matches


def test_stopwords_dropped():
    assert stem_tokens("What is the AMF") == ["amf"]


def test_exact_terms_message_names_timers_causes():
    terms = exact_terms('Does the UE start timer T3510 when it sends an ATTACH REQUEST with cause #28?')
    assert "T3510" in terms
    assert "ATTACH REQUEST" in terms
    assert "#28" in terms


def test_exact_terms_drop_terms_contained_in_longer_ones():
    terms = exact_terms("When the AMF sends a DOWNLINK GENERIC NAS TRANSPORT message")
    assert "DOWNLINK GENERIC NAS TRANSPORT" in terms
    assert "NAS" not in terms


def test_grading_rows_hide_methods_and_are_shuffled():
    by_id = {f"c{i}": {"chunk_id": f"c{i}", "spec_id": "23.501", "clause_id": f"1.{i}",
                       "clause_title": "t", "lineage": [], "content": f"text {i}"} for i in range(20)}
    pools = [{"id": 1, "question": "q", "candidates": [
        {"chunk_id": f"c{i}", "found_by": {"system": i + 1}} for i in range(20)]}]
    rows = grading_rows(pools, by_id)
    assert all("found_by" not in r for r in rows)
    assert [r["chunk_id"] for r in rows] != [f"c{i}" for i in range(20)]
    assert [r["grade_id"] for r in rows] == list(range(1, 21))


def test_answer_chunk_ids_only_under_gold_clauses():
    from src.eval.pool_candidates import answer_chunk_ids

    chunks = [
        {"chunk_id": "a", "spec_id": "24.301", "clause_id": "5.5.1.2.2", "content": "x starting timer T3410 and y"},
        {"chunk_id": "b", "spec_id": "24.301", "clause_id": "5.5.1.2.2", "content": "unrelated text here"},
        {"chunk_id": "c", "spec_id": "24.501", "clause_id": "5.5.1.2.2", "content": "x starting timer T3410 and y"},
    ]
    record = {"gold_clauses": [{"spec_id": "24.301", "clause_id": "5.5.1"}],
              "answer_quotes": ['24.301: "…starting timer T3410…"']}
    assert answer_chunk_ids(record, chunks) == ["a"]
