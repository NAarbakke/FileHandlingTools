import json

from pdftranslate.extract import _join_lines, extract_document, run

REQUIRED_BLOCK_KEYS = {"id", "bbox", "text", "size", "color", "skip", "skip_reason"}


def _ln(text, x1):
    """A line record as produced by PyMuPDF's dict extraction (only x1 matters here)."""
    return {"text": text, "bbox": [0.0, 0.0, x1, 0.0]}


def test_join_lines_reflows_prose():
    # Every line runs to the block's right edge -> soft wraps -> one reflowed line.
    block_bbox = [165.0, 0.0, 560.0, 0.0]
    lines = [
        _ln("This is the first wrapped line", 559.0),
        _ln("and this is the second wrapped line", 559.0),
        _ln("and a short final line.", 300.0),
    ]
    assert _join_lines(lines, block_bbox) == (
        "This is the first wrapped line and this is the second wrapped line "
        "and a short final line."
    )


def test_join_lines_preserves_enumerated_breaks():
    # Superscript markers (1, 2) sit on their own short lines and must attach to
    # the following line; the real ends of each item (short lines) become breaks.
    block_bbox = [165.0, 0.0, 550.0, 0.0]
    lines = [
        _ln("1", 169.0),
        _ln("Department of Mechanical Engineering, Air University", 550.0),
        _ln("Islamabad, Pakistan", 383.0),
        _ln("2", 169.0),
        _ln("Control Engineering Department, King Fahd University", 542.0),
        _ln("Dhahran, Saudi Arabia", 283.0),
    ]
    assert _join_lines(lines, block_bbox) == (
        "1 Department of Mechanical Engineering, Air University Islamabad, Pakistan\n"
        "2 Control Engineering Department, King Fahd University Dhahran, Saudi Arabia"
    )


def test_extract_structure(tiny_pdf):
    doc = extract_document(tiny_pdf, source_lang="en", target_lang="no")
    assert doc["source_lang"] == "en"
    assert doc["target_lang"] == "no"
    assert doc["page_count"] == 1
    assert len(doc["pages"]) == 1
    page = doc["pages"][0]
    assert page["page"] == 0
    assert page["width"] == 300
    assert page["height"] == 200
    assert page["blocks"], "expected at least one text block"
    for b in page["blocks"]:
        assert REQUIRED_BLOCK_KEYS.issubset(b)
        assert len(b["bbox"]) == 4


def test_extract_finds_text(tiny_pdf):
    doc = extract_document(tiny_pdf, source_lang="en", target_lang="no")
    all_text = " ".join(b["text"] for b in doc["pages"][0]["blocks"])
    assert "Hello world" in all_text
    assert "Second line here" in all_text


def test_extract_pages_filter(tiny_pdf):
    doc = extract_document(tiny_pdf, source_lang="en", target_lang="no", pages={5})
    assert doc["page_count"] == 1
    assert doc["pages"] == []


def test_run_writes_json(tiny_pdf, tmp_path):
    out = tmp_path / "blocks.json"
    run(tiny_pdf, str(out), source_lang="en", target_lang="no")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["source_pdf"].endswith("tiny.pdf")
    assert data["pages"][0]["blocks"]
