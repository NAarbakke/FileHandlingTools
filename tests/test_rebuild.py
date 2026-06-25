import fitz

from tools.translate.extract import extract_document
from tools.translate import rebuild


def test_rebuild_redacts_and_inserts(tiny_pdf, tmp_path):
    doc = extract_document(tiny_pdf, source_lang="en", target_lang="no")
    first = doc["pages"][0]["blocks"][0]
    original = first["text"]
    first["text_translated"] = "Hei verden"

    out = tmp_path / "out.pdf"
    rebuild.rebuild_pdf(tiny_pdf, doc, str(out))

    assert out.exists()
    res = fitz.open(str(out))
    try:
        assert res.page_count == 1
        text = res.load_page(0).get_text()
        assert "Hei verden" in text
        assert original not in text
    finally:
        res.close()


def test_rebuild_keeps_page_count(tiny_pdf, tmp_path):
    doc = extract_document(tiny_pdf, source_lang="en", target_lang="no")
    for b in doc["pages"][0]["blocks"]:
        b["text_translated"] = "x"
    out = tmp_path / "out.pdf"
    rebuild.rebuild_pdf(tiny_pdf, doc, str(out))
    src = fitz.open(tiny_pdf)
    res = fitz.open(str(out))
    try:
        assert res.page_count == src.page_count
    finally:
        src.close()
        res.close()
