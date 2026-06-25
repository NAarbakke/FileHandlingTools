from pathlib import Path

import fitz

from tools.transcribe import ingest


def test_ingest_pdf_writes_one_png_per_page(two_page_pdf, tmp_path):
    manifest = ingest.ingest(two_page_pdf, str(tmp_path / "pages"), dpi=150)
    assert manifest["page_count"] == 2
    assert len(manifest["pages"]) == 2
    for p in manifest["pages"]:
        assert Path(p["image"]).exists()
        assert Path(p["image"]).stat().st_size > 0


def test_ingest_image_single_page(tiny_png, tmp_path):
    manifest = ingest.ingest(tiny_png, str(tmp_path / "pages"))
    assert manifest["page_count"] == 1
    assert Path(manifest["pages"][0]["image"]).exists()


def test_ingest_pages_filter_keeps_original_page_number(two_page_pdf, tmp_path):
    manifest = ingest.ingest(two_page_pdf, str(tmp_path / "pages"), pages={1})  # 0-based -> page 2
    assert manifest["page_count"] == 1
    assert manifest["pages"][0]["page"] == 2


def test_ingest_grayscale_produces_single_channel(tiny_png, tmp_path):
    manifest = ingest.ingest(tiny_png, str(tmp_path / "pages"), gray=True)
    pix = fitz.Pixmap(manifest["pages"][0]["image"])
    assert pix.n == 1  # one channel = grayscale
