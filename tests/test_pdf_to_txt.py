from convert.pdf_to_txt import pdf_to_txt


def test_pdf_to_txt_extracts_text(tiny_pdf):
    out = pdf_to_txt(tiny_pdf)
    assert "Hello world" in out
    assert "Second line here" in out


def test_pdf_to_txt_includes_all_pages(two_page_pdf):
    out = pdf_to_txt(two_page_pdf)
    assert "Page 1 text" in out
    assert "Page 2 text" in out
