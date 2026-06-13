import json

from pdftranslate.extract import extract_document, run

REQUIRED_BLOCK_KEYS = {"id", "bbox", "text", "size", "color", "skip", "skip_reason"}


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
