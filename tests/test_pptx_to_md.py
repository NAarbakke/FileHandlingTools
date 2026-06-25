from tools.convert.pptx_to_md import pptx_to_md


def test_pptx_to_md_returns_markdown_with_text(tiny_pptx):
    out = pptx_to_md(tiny_pptx)
    assert isinstance(out, str)
    assert "Slide Title" in out
    assert "Slide body content." in out
