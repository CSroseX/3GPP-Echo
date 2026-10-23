"""Tests for tree_builder: list groups must be expanded in reading order, not skipped."""

import json

from src.ingestion.tree_builder import build_tree


def _text(i, label, text, parent="#/body"):
    return {"self_ref": f"#/texts/{i}", "parent": {"$ref": parent}, "label": label, "text": text}


def _build(tmp_path, doc):
    src, out = tmp_path / "parsed.json", tmp_path / "tree.json"
    src.write_text(json.dumps(doc), encoding="utf-8")
    build_tree(str(src), str(out))
    return json.loads(out.read_text(encoding="utf-8"))


def test_list_items_kept_in_reading_order_including_nested_lists(tmp_path):
    doc = {
        "body": {"children": [{"$ref": "#/texts/0"}, {"$ref": "#/texts/1"},
                              {"$ref": "#/groups/0"}, {"$ref": "#/texts/5"}]},
        "texts": [
            _text(0, "section_header", "6.2.1 AMF"),
            _text(1, "text", "The AMF includes the following functionality:"),
            _text(2, "list_item", "-Registration management.", "#/groups/0"),
            _text(3, "list_item", "-Connection management.", "#/groups/0"),
            _text(4, "list_item", "-Nested item.", "#/groups/1"),
            _text(5, "text", "NOTE 1: Trailing paragraph."),
        ],
        "groups": [
            {"self_ref": "#/groups/0", "label": "list",
             "children": [{"$ref": "#/texts/2"}, {"$ref": "#/groups/1"}, {"$ref": "#/texts/3"}]},
            {"self_ref": "#/groups/1", "label": "list", "children": [{"$ref": "#/texts/4"}]},
        ],
        "tables": [],
    }
    clauses = _build(tmp_path, doc)
    amf = next(c for c in clauses if c["clause_id"] == "6.2.1")
    assert [item["text"] for item in amf["content"]] == [
        "The AMF includes the following functionality:",
        "-Registration management.",
        "-Nested item.",
        "-Connection management.",
        "NOTE 1: Trailing paragraph.",
    ]


def test_ie_diagram_bit_row_is_not_a_clause_heading(tmp_path):
    doc = {
        "body": {"children": [{"$ref": "#/texts/0"}, {"$ref": "#/texts/1"}, {"$ref": "#/texts/2"}]},
        "texts": [
            _text(0, "section_header", "9.9.3.17 Identity type 2"),
            _text(1, "section_header", "8 7 6 5  4 3 2 1 Type"),
            _text(2, "text", "Identity type 2 IEI"),
        ],
        "groups": [],
        "tables": [],
    }
    clauses = _build(tmp_path, doc)
    assert [c["clause_id"] for c in clauses] == ["0", "9.9.3.17"]
    assert [item["text"] for item in clauses[1]["content"]] == ["8 7 6 5  4 3 2 1 Type", "Identity type 2 IEI"]
