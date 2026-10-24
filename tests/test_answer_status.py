"""parse_status and the identifier check (src/generation/answer_status.py)."""

from src.generation.answer_status import check_identifiers, find_identifiers, normalize_text, parse_status


class TestParseStatus:
    def test_reads_and_strips_the_status_line(self):
        assert parse_status("The AMF handles registration.\n\nSTATUS: answered") == (
            "The AMF handles registration.", "answered")

    def test_accepts_markdown_and_spacing_variants(self):
        assert parse_status("Text.\n**STATUS: Partial**")[1] == "partial"
        assert parse_status("Text.\nstatus : not covered")[1] == "not_covered"
        assert parse_status("Text.\nSTATUS: not-covered.")[1] == "not_covered"

    def test_missing_line_returns_none(self):
        assert parse_status("Just an answer.") == ("Just an answer.", None)

    def test_last_status_line_wins_and_all_are_removed(self):
        text, status = parse_status("A.\nSTATUS: answered\nB.\nSTATUS: partial")
        assert status == "partial" and "STATUS" not in text

    def test_status_word_inside_prose_is_not_a_status_line(self):
        assert parse_status("The EPS update STATUS: answered is not a field.")[1] is None


class TestIdentifierCheck:
    def test_finds_timers_causes_and_message_names(self):
        ids = find_identifiers("The UE starts T3510, sends a REGISTRATION REQUEST and gets cause #22.")
        assert ids == ["T3510", "#22", "REGISTRATION REQUEST"]

    def test_acronym_pairs_are_not_message_names(self):
        assert find_identifiers("the AMF does not perform EPS TAU, unlike the DL NAS TRANSPORT") == [
            "DL NAS TRANSPORT"]

    def test_identifiers_present_in_sources_pass(self):
        source = "the UE sends a registration request message, starting timer T3510"
        assert check_identifiers("It starts T3510 with the REGISTRATION REQUEST.", source) == []

    def test_missing_identifiers_are_reported(self):
        assert check_identifiers("It starts T3410 and gets #22.", "starting timer T3510") == ["T3410", "#22"]

    def test_timer_must_match_whole_token(self):
        assert check_identifiers("T351", "timer T3510") == []  # not an identifier (3 digits)
        assert check_identifiers("T3510", "timer T35100") == ["T3510"]


class TestNormalizeText:
    def test_typographic_spaces_and_hyphens_become_ascii(self):
        text = normalize_text("DOWNLINK GENERIC NAS TRANSPORT and 5G‑GUTI")
        assert text == "DOWNLINK GENERIC NAS TRANSPORT and 5G-GUTI"
        assert find_identifiers(text) == ["DOWNLINK GENERIC NAS TRANSPORT"]
