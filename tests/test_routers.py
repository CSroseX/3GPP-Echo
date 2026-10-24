from src.generation.routers import after_cache, after_triage


class TestPhase4RoutersCrossProduct:
    """The Phase 4 routers over the cross-product of the state fields they
    read (and fields they must ignore)."""

    def test_after_triage(self):
        for decision in (None, "in_domain", "out_of_domain"):
            for tier in (None, "lexical", "centroid", "llm", "fail_open"):
                for termination_reason in (None, "out_of_domain"):
                    state = {"triage_decision": decision, "triage_tier": tier,
                             "termination_reason": termination_reason}
                    expected = "refuse" if decision == "out_of_domain" else "retrieve"
                    assert after_triage(state) == expected, state

    def test_after_cache(self):
        for hit in (None, "exact", "semantic"):
            assert after_cache({"cache_hit": hit}) == ("hit" if hit else "triage")
