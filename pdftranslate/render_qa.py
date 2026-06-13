"""Stage 4: render the first N pages of original and translated PDFs to PNGs."""
from __future__ import annotations

from pathlib import Path

import fitz


def render_pages(pdf_path, out_dir, prefix, pages=3, dpi=150):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pdf = fitz.open(pdf_path)
    try:
        n = min(pages, pdf.page_count)
        written = []
        for pno in range(n):
            pix = pdf.load_page(pno).get_pixmap(matrix=mat)
            p = out / f"{prefix}_p{pno + 1}.png"
            pix.save(str(p))
            written.append(p)
        return written
    finally:
        pdf.close()


def run(original_pdf, translated_pdf, out_dir, pages=3, dpi=150):
    render_pages(original_pdf, out_dir, "original", pages=pages, dpi=dpi)
    render_pages(translated_pdf, out_dir, "translated", pages=pages, dpi=dpi)
