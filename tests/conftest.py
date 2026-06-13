import fitz
import pytest


@pytest.fixture
def tiny_pdf(tmp_path):
    """A 1-page PDF with two text lines and one vector 'figure' (a filled rect)."""
    path = tmp_path / "tiny.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((20, 40), "Hello world", fontsize=12)
    page.insert_text((20, 80), "Second line here", fontsize=12)
    page.draw_rect(fitz.Rect(20, 110, 120, 170), color=(0, 0, 1), fill=(0.8, 0.8, 1.0))
    doc.save(str(path))
    doc.close()
    return str(path)
