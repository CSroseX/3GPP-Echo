"""AnswerCache: exact and semantic hits, and the same-3GPP-terms rule."""

import numpy as np

from src.generation.answer_cache import AnswerCache, domain_terms, normalize


class FakeLexicon:
    def find_acronyms(self, text):
        return [t for t in ("AMF", "MME", "TAU") if t in text]

    def find_long_forms(self, text):
        return []


def embed_by_topic(texts):
    """Questions about timers embed together; everything else elsewhere."""
    return np.array([[1.0, 0.0] if "timer" in t.lower() else [0.0, 1.0] for t in texts], dtype=np.float32)


def make_cache(tmp_path):
    return AnswerCache(tmp_path / "cache.sqlite", embed=embed_by_topic, lexicon=FakeLexicon(), similarity=0.95)


def test_normalize_ignores_case_punctuation_and_spacing():
    assert normalize("What is the AMF?") == normalize("what is the   amf")


def test_exact_hit_after_normalization(tmp_path):
    cache = make_cache(tmp_path)
    cache.store("What is the AMF?", "The AMF ...", [{"spec_id": "23.501", "clause_id": "6.2.1"}])
    hit = cache.lookup("what is the AMF")
    assert hit["answer"] == "The AMF ..." and hit["match"] == "exact"


def test_semantic_hit_needs_same_terms(tmp_path):
    cache = make_cache(tmp_path)
    cache.store("What timer does the AMF use for TAU?", "5G answer", [])
    hit = cache.lookup("Which timer is used by the AMF for TAU")
    assert hit["answer"] == "5G answer" and hit["match"] == "semantic"


def test_same_meaning_different_entity_is_a_miss(tmp_path):
    # Embeds identically, but MME (4G) is not AMF (5G): a different answer.
    cache = make_cache(tmp_path)
    cache.store("What timer does the AMF use for TAU?", "5G answer", [])
    assert cache.lookup("What timer does the MME use for TAU?") is None


def test_dissimilar_question_is_a_miss(tmp_path):
    cache = make_cache(tmp_path)
    cache.store("What timer does the AMF use for TAU?", "5G answer", [])
    assert cache.lookup("How is the AMF selected for TAU?") is None


def test_domain_terms_include_spec_numbers():
    assert domain_terms("What does TS 23.501 say about the AMF?", FakeLexicon()) == ["23.501", "AMF"]
