"""Corpus-derived lexicon: long-form matching on synthetic text, and the
real lexicon built from data/chunks/ (no network, no models)."""

import pytest

from src.generation.lexicon import (
    build_lexicon,
    find_long_form,
    get_lexicon,
    is_acronym_shaped,
)


class TestIsAcronymShaped:
    def test_acronyms(self):
        for tok in ["AMF", "5GS", "gNB", "QoS", "5G-GUTI", "NG-RAN", "UE"]:
            assert is_acronym_shaped(tok), tok

    def test_not_acronyms(self):
        for tok in ["What", "France", "2022", "a", "the"]:
            assert not is_acronym_shaped(tok), tok


class TestFindLongForm:
    def test_plain_initials(self):
        assert find_long_form("MME", "is served by the Mobility Management Entity") == "Mobility Management Entity"

    def test_skips_one_interior_word(self):
        # AMF does not spell "Mobility"; one interior content word may be skipped.
        assert (
            find_long_form("AMF", "the Access and Mobility Management Function")
            == "Access and Mobility Management Function"
        )

    def test_function_word_can_spell(self):
        assert find_long_form("QoS", "the Quality of Service") == "Quality of Service"

    def test_acronym_word_spells_a_run(self):
        assert find_long_form("5GMM", "the 5GS Mobility Management") == "5GS Mobility Management"

    def test_rejects_merged_table_row(self):
        # Docling merged two abbreviation rows into one; it must not vote.
        assert find_long_form("NSSAI", "Network Slice Selection Assistance Network Slice Selection Function") is None

    def test_rejects_unrelated_words(self):
        assert find_long_form("NOTE", "no QCI requested") is None


def _chunk(spec_id, clause_id, content, title="General", chunk_type="text"):
    return {
        "spec_id": spec_id,
        "clause_id": clause_id,
        "clause_title": title,
        "chunk_type": chunk_type,
        "content": content,
    }


@pytest.fixture
def low_min_freq(monkeypatch):
    from src.config import get_settings

    monkeypatch.setenv("LEXICON_MIN_TERM_FREQ", "2")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("LEXICON_MIN_TERM_FREQ")
    get_settings.cache_clear()


@pytest.mark.usefixtures("low_min_freq")
class TestBuildLexiconSynthetic:
    def make(self, monkeypatch):
        chunks = [
            _chunk("24.301", "4.1", "The Mobility Management Entity (MME) serves the UE. MME MME MME."),
            _chunk("24.301", "4.2", "The MME and the UE. NOTE: the MME. NOTE: a note. Note that."),
            _chunk("23.501", "6.2.1", "The Access and Mobility Management Function (AMF) serves the UE. AMF AMF."),
            _chunk("23.501", "6.2.2", "The AMF and UE.", title="PDU Session establishment"),
            _chunk("23.501", "9", "CP-123456 CP-123456 CP-123456", title="Change history"),
            _chunk("23.501", "3.2", [["AMF", "Access and Mobility Management Function"]],
                   title="Abbreviations", chunk_type="table"),
        ]
        return build_lexicon(chunks)

    def test_long_forms_harvested(self, monkeypatch):
        lex = self.make(monkeypatch)
        assert lex.long_forms["MME"] == "Mobility Management Entity"
        assert lex.long_forms["AMF"] == "Access and Mobility Management Function"

    def test_capitalised_english_is_not_an_acronym(self, monkeypatch):
        lex = self.make(monkeypatch)
        assert "NOTE" not in lex.acronyms

    def test_change_history_is_ignored(self, monkeypatch):
        lex = self.make(monkeypatch)
        assert "CP-123456" not in lex.acronyms

    def test_generation_affinity_is_measured(self, monkeypatch):
        lex = self.make(monkeypatch)
        assert lex.generation_of("MME") == "4g"
        assert lex.generation_of("AMF") == "5g"
        assert lex.generation_of("UE") is None  # balanced across specs

    def test_title_bigrams(self, monkeypatch):
        lex = self.make(monkeypatch)
        assert ("session", "establishment") in lex.title_bigrams
        assert lex.find_title_bigrams("How is a PDU session establishment triggered?") == [
            "pdu session", "session establishment",
        ]


class TestRealCorpusLexicon:
    def test_core_network_functions_expand(self):
        lex = get_lexicon()
        assert lex.long_forms["AMF"] == "Access and Mobility Management Function"
        assert lex.long_forms["MME"] == "Mobility Management Entity"
        assert lex.long_forms["SMF"] == "Session Management Function"

    def test_generation_affinity(self):
        lex = get_lexicon()
        for ac in ("MME", "EMM", "ESM", "EPS"):
            assert lex.generation_of(ac) == "4g", ac
        for ac in ("AMF", "UDM", "SMF", "5GMM"):
            assert lex.generation_of(ac) == "5g", ac

    def test_generic_one_off_terms_excluded(self):
        lex = get_lexicon()
        # Mentioned once or twice in the corpus: not domain vocabulary.
        assert "XML" not in lex.acronyms
        assert "HTTP" not in lex.acronyms

    def test_find_long_forms_reverse_direction(self):
        lex = get_lexicon()
        hits = lex.find_long_forms("What does the access and mobility management function do?")
        assert ("access and mobility management function", "AMF") in hits


class TestPhraseGeneration:
    def make(self, monkeypatch):
        monkeypatch.setenv("REWRITE_PHRASE_MIN_FREQ", "2")
        monkeypatch.setenv("REWRITE_PHRASE_AFFINITY_RATIO", "2")
        get_settings_cache_clear()
        chunks = [
            _chunk("24.301", "5.5", "The UE sends an attach request. Attach request again. Attach request."),
            _chunk("24.501", "5.5", "The UE sends a registration request. Registration request. 5GMM state."),
            _chunk("24.301", "5.6", "5GMM state 5GMM state 5GMM state handling in interworking."),
        ]
        lex = build_lexicon(chunks)
        monkeypatch.delenv("REWRITE_PHRASE_MIN_FREQ")
        monkeypatch.delenv("REWRITE_PHRASE_AFFINITY_RATIO")
        get_settings_cache_clear()
        return lex

    def test_phrase_affinity_is_measured(self, monkeypatch):
        lex = self.make(monkeypatch)
        assert lex.find_generation_phrases("Does an Attach Request reach the AMF?") == [("attach request", "4g")]
        assert ("registration request", "5g") in lex.find_generation_phrases("a registration request")

    def test_generation_prefixed_words_are_left_to_naming_rule(self, monkeypatch):
        lex = self.make(monkeypatch)
        assert lex.find_generation_phrases("which 5GMM state") == []


def get_settings_cache_clear():
    from src.config import get_settings

    get_settings.cache_clear()
