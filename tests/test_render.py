import fitz
from docx import Document

from transcribe import render


def make_transcript():
    return {
        "source": "n.png", "model": "m",
        "pages": [{
            "page": 1, "image": "a.png",
            "markdown": "# Title\n\nHello world.\n\n- item one\n- item two\n\n1. first\n2. second",
        }],
    }


def test_md_to_blocks_parses_headings_lists_paragraphs():
    blocks = render.md_to_blocks("# Title\n\nSome text.\n\n- a\n- b\n\n1. one\n2. two")
    assert blocks[0] == {"type": "heading", "level": 1, "text": "Title"}
    assert blocks[1] == {"type": "paragraph", "text": "Some text."}
    assert blocks[2]["type"] == "list_item" and blocks[2]["ordered"] is False and blocks[2]["text"] == "a"
    assert blocks[3]["ordered"] is False and blocks[3]["text"] == "b"
    assert blocks[4]["ordered"] is True and blocks[4]["text"] == "one"
    assert blocks[5]["ordered"] is True and blocks[5]["text"] == "two"


def test_md_to_blocks_reflows_wrapped_paragraph():
    blocks = render.md_to_blocks("This is one\nparagraph split\nover lines.")
    assert blocks == [{"type": "paragraph", "text": "This is one paragraph split over lines."}]


def test_render_md_writes_markdown(tmp_path):
    out = render.render_md(make_transcript(), str(tmp_path / "n.md"))
    text = open(out, encoding="utf-8").read()
    assert "# Title" in text and "item one" in text


def test_render_txt_strips_markdown(tmp_path):
    render.render_txt(make_transcript(), str(tmp_path / "n.txt"))
    text = open(tmp_path / "n.txt", encoding="utf-8").read()
    assert "Title" in text and "# Title" not in text
    assert "Hello world." in text


def test_render_docx_is_openable_and_has_text(tmp_path):
    render.render_docx(make_transcript(), str(tmp_path / "n.docx"))
    doc = Document(str(tmp_path / "n.docx"))
    joined = "\n".join(p.text for p in doc.paragraphs)
    assert "Title" in joined and "Hello world." in joined and "item one" in joined


def test_render_pdf_is_openable_and_has_text(tmp_path):
    render.render_pdf(make_transcript(), str(tmp_path / "n.pdf"))
    pdf = fitz.open(str(tmp_path / "n.pdf"))
    try:
        text = "".join(pdf.load_page(i).get_text() for i in range(pdf.page_count))
    finally:
        pdf.close()
    assert "Title" in text and "Hello world." in text and "item one" in text


def test_render_dispatch_writes_all_requested_formats(tmp_path):
    written = render.render(make_transcript(), str(tmp_path), "n", ["md", "txt", "docx", "pdf"])
    assert set(written) == {"md", "txt", "docx", "pdf"}
    for path in written.values():
        from pathlib import Path
        assert Path(path).exists()
