from src.ingestion.chunk_ids import assign_chunk_ids, point_id_for
from src.retrieval.hybrid import BM25Index, chunk_text, rrf_fuse, tokenize


def chunk(spec_id, clause_id, title, content):
    return {"spec_id": spec_id, "clause_id": clause_id, "clause_title": title, "content": content}


CHUNKS = [
    chunk("23.501", "5.15.2", "Identification of a Network Slice", "An S-NSSAI identifies a network slice."),
    chunk("23.501", "6.2.1", "AMF", "The AMF includes registration management and connection management."),
    chunk("24.301", "5.5.3", "Tracking area updating procedure", "Timer T3412 controls periodic tracking area updating."),
    chunk("24.501", "5.5.1", "Registration procedure", "The UE initiates registration with the AMF."),
    # Filler so no query term sits in half the corpus (BM25Okapi gives such
    # terms zero IDF, which a 4-chunk corpus would hit constantly).
    chunk("23.501", "5.6.1", "Session management", "PDU sessions provide connectivity to a data network."),
    chunk("23.501", "5.7.1", "QoS model", "The QoS flow is the finest granularity of QoS differentiation."),
    chunk("24.301", "6.4.1", "Bearer context", "Default EPS bearer context activation."),
    chunk("24.501", "8.2.1", "Message functional definitions", "This clause defines message contents."),
]


class TestTokenize:
    def test_drops_question_framing(self):
        assert tokenize("What is the role of the AMF?") == ["role", "amf"]

    def test_splits_hyphenated_acronyms(self):
        assert tokenize("S-NSSAI") == ["s", "nssai"]

    def test_keeps_alphanumeric_timer_names(self):
        assert tokenize("T3412 expiry") == ["t3412", "expiry"]


class TestChunkText:
    def test_flattens_table_grid(self):
        table = chunk("24.301", "9.9", "Timers", [["Timer", "Value"], ["T3412", "54 min"]])
        assert "T3412 54 min" in chunk_text(table)

    def test_includes_lineage_header(self):
        assert chunk_text(CHUNKS[1]).startswith("Spec 23.501 Clause 6.2.1 AMF")


class TestBM25Index:
    def test_acronym_query_hits_hyphenated_form(self):
        hits = BM25Index(CHUNKS).search("NSSAI", k=3)
        assert hits[0][0]["clause_id"] == "5.15.2"

    def test_exact_timer_name(self):
        hits = BM25Index(CHUNKS).search("What does T3412 do?", k=1)
        assert hits[0][0]["clause_id"] == "5.5.3"

    def test_spec_filter(self):
        hits = BM25Index(CHUNKS).search("AMF registration", k=5, spec_id="24.501")
        assert [h[0]["clause_id"] for h in hits] == ["5.5.1"]

    def test_clause_filter(self):
        hits = BM25Index(CHUNKS).search("AMF registration", k=5, clause_ids=["6.2.1"])
        assert [h[0]["clause_id"] for h in hits] == ["6.2.1"]

    def test_no_overlap_returns_nothing(self):
        assert BM25Index(CHUNKS).search("capital of France", k=5) == []

    def test_k_caps_results(self):
        assert len(BM25Index(CHUNKS).search("AMF registration", k=1)) == 1


class TestRRF:
    def test_item_in_both_rankings_wins(self):
        assert rrf_fuse([["a", "b", "c"], ["c", "d"]])[0] == "c"

    def test_scores_are_reciprocal_rank(self):
        # a: 1/61; b: 1/62 + 1/61 → b first.
        assert rrf_fuse([["a", "b"], ["b"]], k=60) == ["b", "a"]

    def test_ties_keep_first_seen_order(self):
        assert rrf_fuse([["a"], ["b"]]) == ["a", "b"]

    def test_empty(self):
        assert rrf_fuse([[], []]) == []


class TestChunkIds:
    def test_ordinal_disambiguates_shared_clause_ids(self):
        chunks = [chunk("23.501", "0", "Frontmatter", "x"), chunk("23.501", "0", "Frontmatter", "y")]
        assign_chunk_ids(chunks)
        assert chunks[0]["chunk_id"] != chunks[1]["chunk_id"]

    def test_deterministic(self):
        a, b = [dict(c) for c in CHUNKS], [dict(c) for c in CHUNKS]
        assign_chunk_ids(a)
        assign_chunk_ids(b)
        assert [c["chunk_id"] for c in a] == [c["chunk_id"] for c in b]

    def test_matches_original_indexer_formula(self):
        import hashlib

        chunks = [dict(CHUNKS[1])]
        assign_chunk_ids(chunks)
        assert chunks[0]["chunk_id"] == hashlib.sha1(b"23.501|6.2.1|0").hexdigest()

    def test_point_id_is_uuid_shaped(self):
        import uuid

        assert str(uuid.UUID(point_id_for("a" * 40))) == point_id_for("a" * 40)
