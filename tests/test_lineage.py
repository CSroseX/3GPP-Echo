from src.retrieval.lineage import lineage_match

AMF_LINEAGE = ["Frontmatter", "6 Network Functions", "6.2 Network Function Functional description", "6.2.1 AMF"]


class TestLineageMatch:
    def test_own_title_fully_named(self):
        assert lineage_match("What is the role of the AMF?", "AMF", AMF_LINEAGE) == 1.0

    def test_no_overlap(self):
        assert lineage_match("What is the capital of France?", "AMF", AMF_LINEAGE) == 0.0

    def test_partial_title_overlap(self):
        # {smf, discov, select} vs query stems: smf + select → 2/3.
        score = lineage_match("Which function is responsible for selecting the SMF?", "SMF discovery and selection",
                              ["6 Network Functions", "6.3 Principles for Network Function Discovery and Selection",
                               "6.3.2 SMF discovery and selection"])
        assert abs(score - 2 / 3) < 1e-9

    def test_ancestor_match_is_halved(self):
        lineage = ["5 High level features", "5.15 Network slicing", "5.15.2 Identification"]
        assert lineage_match("network slicing", "Identification", lineage) == 0.5

    def test_frontmatter_ignored(self):
        assert lineage_match("frontmatter", "Frontmatter", ["Frontmatter"]) == 0.0

    def test_empty_query(self):
        assert lineage_match("the of", "AMF", AMF_LINEAGE) == 0.0

    def test_letter_suffixed_clause_number_stripped(self):
        lineage = ["4 Architecture", "4.2.8 Support of non-3GPP access", "4.2.8.1A General"]
        assert lineage_match("non-3GPP access support", "General", lineage) == 0.5
