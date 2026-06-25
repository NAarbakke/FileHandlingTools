"""Stage 3: rebuild the PDF — redact original text, insert translated text.

Figures, photos, and vector graphics are preserved by removing ONLY text during
redaction (images and line-art are explicitly kept).
"""
from __future__ import annotations

from pathlib import Path

import fitz

from core import ASSETS

from .common import color_int_to_rgb

FONT_FILE = ASSETS / "DejaVuSans.ttf"
FONT_NAME = "djv"
MIN_FONT_SIZE = 4.0


def _insert_fit(page, rect, text, size, color):
    """Insert text into rect, shrinking the font until it fits (down to a floor)."""
    fs = float(size)
    font_file_str = str(FONT_FILE)
    while fs >= MIN_FONT_SIZE:
        rc = page.insert_textbox(
            rect, text,
            fontname=FONT_NAME, fontfile=font_file_str,
            fontsize=fs, color=color, align=0,
        )
        if rc >= 0:
            return
        fs -= 0.5
    page.insert_textbox(
        rect, text,
        fontname=FONT_NAME, fontfile=font_file_str,
        fontsize=MIN_FONT_SIZE, color=color, align=0,
    )


def rebuild_pdf(src_pdf, doc, out_path):
    """Write a translated copy of `src_pdf` using translations in `doc` (blocks.no)."""
    pdf = fitz.open(src_pdf)
    try:
        for page_data in doc["pages"]:
            page = pdf.load_page(page_data["page"])
            targets = [b for b in page_data["blocks"]
                       if not b.get("skip") and "text_translated" in b]
            if not targets:
                continue
            # 1) remove original text (keep images + vector graphics)
            for blk in targets:
                page.add_redact_annot(fitz.Rect(blk["bbox"]), fill=(1, 1, 1), cross_out=False)
            page.apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_NONE,
                graphics=fitz.PDF_REDACT_LINE_ART_NONE,
            )
            # 2) insert translated text into the same boxes (after redactions)
            for blk in targets:
                _insert_fit(
                    page,
                    fitz.Rect(blk["bbox"]),
                    blk["text_translated"],
                    blk["size"],
                    color_int_to_rgb(blk.get("color", 0)),
                )
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        pdf.save(str(out), garbage=4, deflate=True)
    finally:
        pdf.close()
