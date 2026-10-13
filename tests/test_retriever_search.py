"""Retriever.search() with Qdrant, the embedder and the cross-encoder faked:
candidate-pool sizing and rerank ordering, no network or model downloads."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.config import Settings
from src.ingestion.chunk_ids import assign_chunk_ids

CHUNKS = [
    {"spec_id": "23.501", "clause_id": "6.2.1", "clause_title": "AMF",
     "lineage": ["6 Network Function functional description", "6.2 Network Function Functional description", "6.2.1 AMF"],
     "content": "The Access and Mobility Management Function (AMF) includes registration management."},
    {"spec_id": "23.501", "clause_id": "5.3.2", "clause_title": "Registration management",
     "lineage": ["5 High level features", "5.3 Registration and Connection Management", "5.3.2 Registration management"],
     "content": "Registration management is used to register or deregister a UE with the network."},
    {"spec_id": "24.301", "clause_id": "5.5.3", "clause_title": "Tracking area updating procedure",
     "lineage": ["5 EPS mobility management", "5.5 EMM common procedures", "5.5.3 Tracking area updating procedure"],
     "content": "The tracking area updating procedure uses timer T3412 in EPS."},
]


def make_settings(**overrides):
    return Settings(**overrides)


@pytest.fixture
def make_retriever(tmp_path):
    """Build a Retriever over CHUNKS with fake Qdrant/embedder/cross-encoder.
    qdrant_order is the dense ranking (indices into CHUNKS); cross_scores maps
    clause_id → cross-encoder score."""
    (tmp_path / "src").mkdir()
    (tmp_path / "data" / "chunks").mkdir(parents=True)
    (tmp_path / "data" / "chunks" / "test_chunks.json").write_text(json.dumps(CHUNKS), encoding="utf-8")

    def build(qdrant_order=(0, 1, 2), cross_scores=None, **setting_overrides):
        cfg = make_settings(**setting_overrides)
        cross_scores = cross_scores or {}

        q_client = MagicMock()

        # Payloads carry chunk_id, as the indexer stores them.
        payloads = [dict(c) for c in CHUNKS]
        assign_chunk_ids(payloads)

        def query_points(collection_name, query, query_filter, limit):
            points = [
                SimpleNamespace(payload=payloads[i], score=1.0 - 0.1 * rank)
                for rank, i in enumerate(qdrant_order)
            ][:limit]
            return SimpleNamespace(points=points)

        q_client.query_points.side_effect = query_points

        embedder = MagicMock()
        embedder.embed.side_effect = lambda texts: iter([np.zeros(4) for _ in texts])

        cross_encoder = MagicMock()

        def predict(pairs):
            by_content = {c["content"]: cross_scores.get(c["clause_id"], 0.0) for c in CHUNKS}
            return [by_content[text] for _, text in pairs]

        cross_encoder.predict.side_effect = predict

        with patch("src.retrieval.retriever.get_settings", return_value=cfg), \
                patch.object(Settings, "project_root", new=property(lambda self: tmp_path)), \
                patch("src.retrieval.retriever.QdrantClient", return_value=q_client), \
                patch("src.retrieval.retriever.TextEmbedding", return_value=embedder), \
                patch("src.retrieval.retriever.CrossEncoder", return_value=cross_encoder):
            from src.retrieval.retriever import Retriever
            retriever = Retriever()

        def search(*args, **kwargs):
            with patch("src.retrieval.retriever.get_settings", return_value=cfg):
                return retriever.search(*args, **kwargs)

        return SimpleNamespace(retriever=retriever, search=search, q_client=q_client, cfg=cfg)

    return build


class TestCandidatePool:
    def test_candidate_k_defaults_to_multiplier_times_top_k(self, make_retriever):
        r = make_retriever(rerank_multiplier=8)
        r.search("What is the AMF?", top_k=5)
        assert r.q_client.query_points.call_args.kwargs["limit"] == 40

    def test_top_k_5_and_20_no_longer_share_a_pool(self, make_retriever):
        r = make_retriever(rerank_multiplier=8)
        r.search("What is the AMF?", top_k=5)
        r.search("What is the AMF?", top_k=20)
        limits = [c.kwargs["limit"] for c in r.q_client.query_points.call_args_list]
        assert limits == [40, 160]

    def test_explicit_candidate_k_overrides_multiplier(self, make_retriever):
        r = make_retriever(rerank_multiplier=8)
        r.search("What is the AMF?", top_k=20, candidate_k=40)
        assert r.q_client.query_points.call_args.kwargs["limit"] == 40

    def test_candidate_k_never_below_top_k(self, make_retriever):
        r = make_retriever()
        r.search("What is the AMF?", top_k=10, candidate_k=3)
        assert r.q_client.query_points.call_args.kwargs["limit"] == 10


class TestRerankOrdering:
    def test_results_sorted_by_cross_encoder_and_truncated(self, make_retriever):
        r = make_retriever(cross_scores={"6.2.1": 0.2, "5.3.2": 0.9, "5.5.3": -1.0})
        results = r.search("What is the AMF?", top_k=2)
        assert [c["clause_id"] for c in results] == ["5.3.2", "6.2.1"]
        assert results[0]["score"] == 0.9


class TestHybridFusion:
    def test_bm25_only_hit_reaches_the_reranker(self, make_retriever):
        # Dense misses the AMF chunk entirely; BM25 matches "AMF" lexically.
        r = make_retriever(qdrant_order=(1, 2), cross_scores={"6.2.1": 5.0, "5.3.2": 1.0, "5.5.3": 0.0})
        results = r.search("AMF", top_k=1)
        assert results[0]["clause_id"] == "6.2.1"
        assert results[0]["qdrant_score"] is None
        assert results[0]["bm25_score"] > 0

    def test_hybrid_disabled_is_dense_only(self, make_retriever):
        r = make_retriever(qdrant_order=(1, 2), cross_scores={"6.2.1": 5.0}, hybrid_bm25=False)
        assert r.retriever.bm25 is None
        results = r.search("AMF", top_k=3)
        assert "6.2.1" not in [c["clause_id"] for c in results]

    def test_chunk_found_by_both_paths_is_not_duplicated(self, make_retriever):
        r = make_retriever(qdrant_order=(0, 1, 2))
        results = r.search("AMF registration", top_k=10)
        ids = [c["chunk_id"] for c in results]
        assert len(ids) == len(set(ids)) == 3

    def test_bm25_respects_spec_targeting(self, make_retriever):
        r = make_retriever(qdrant_order=())
        results = r.search("tracking area timer T3412 in TS 24.301", top_k=5)
        assert {c["spec_id"] for c in results} == {"24.301"}


class TestLineageBoost:
    def test_boost_lifts_title_match_over_close_competitor(self, make_retriever):
        # Cross-encoder slightly prefers 5.3.2; the query names the AMF clause.
        scores = {"6.2.1": 1.0, "5.3.2": 1.5, "5.5.3": -5.0}
        r = make_retriever(cross_scores=scores, lineage_boost=2.0)
        results = r.search("What is the role of the AMF?", top_k=1)
        assert results[0]["clause_id"] == "6.2.1"
        assert results[0]["cross_score"] == 1.0
        assert results[0]["lineage_match"] == 1.0
        assert results[0]["score"] == 3.0

    def test_default_boost_is_off(self, make_retriever):
        scores = {"6.2.1": 1.0, "5.3.2": 1.5, "5.5.3": -5.0}
        r = make_retriever(cross_scores=scores)
        results = r.search("What is the role of the AMF?", top_k=1)
        assert results[0]["clause_id"] == "5.3.2"
        assert results[0]["score"] == results[0]["cross_score"]
