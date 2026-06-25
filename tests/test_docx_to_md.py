from tools.convert.docx_to_md import docx_to_md


def test_docx_to_md_returns_markdown_with_text(tiny_docx):
    out = docx_to_md(tiny_docx)
    assert isinstance(out, str)
    assert "Docx Title" in out
    assert "Body paragraph text." in out
