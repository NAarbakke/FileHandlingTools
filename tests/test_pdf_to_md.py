from tools.convert.pdf_to_md import pdf_to_md


def test_pdf_to_md_returns_markdown_with_text(tiny_pdf):
    out = pdf_to_md(tiny_pdf)
    assert isinstance(out, str)
    assert "Hello world" in out
