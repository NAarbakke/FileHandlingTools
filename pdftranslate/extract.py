"""Stage 1: extract text blocks (with positions) from a PDF into blocks.json."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

from .common import looks_untranslatable

# A line whose right edge falls more than this fraction of the block width short
# of the block's right edge is treated as a hard line break (e.g. the end of a
# list item) rather than a soft word-wrap to be reflowed.
SHORT_LINE_FRAC = 0.2

# Lone enumeration markers (superscript "1", "2", a "*", a dagger) land on their
# own line in PyMuPDF's output; they belong with the line that follows, so they
# never start a hard break.
_MARKER_RE = re.compile(r"^(\d{1,2}[.)]?|[*†‡§¶#])$")


def _is_marker(text):
    return bool(_MARKER_RE.match(text.strip()))


def _join_lines(lines, block_bbox):
    """Join a block's lines, preserving hard breaks as '\\n' and reflowing soft wraps.

    `lines` is a list of dicts with "text" and a PyMuPDF "bbox" (x0, y0, x1, y1).
    A line that ends well short of the block's right edge is a hard break; a
    full-width line is a soft wrap joined with a space. Lone enumeration markers
    attach to the next line instead of forcing a break after themselves.
    """
    if not lines:
        return ""
    bx0, _, bx1, _ = block_bbox
    width = (bx1 - bx0) or 1.0
    parts = [lines[0]["text"]]
    for prev, cur in zip(lines, lines[1:]):
        prev_short = (bx1 - prev["bbox"][2]) > SHORT_LINE_FRAC * width
        hard = prev_short and not _is_marker(prev["text"])
        parts.append(("\n" if hard else " ") + cur["text"])
    return "".join(parts)


def _extract_page(page, pno):
    data = page.get_text("dict")
    blocks = []
    bidx = 0
    for block in data.get("blocks", []):
        if block.get("type", 0) != 0:
            continue  # image block — left untouched in the PDF
        block_lines = []
        sizes = []
        first_color = 0
        have_color = False
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            line_text = "".join(s.get("text", "") for s in spans)
            if line_text:
                block_lines.append({"text": line_text, "bbox": line["bbox"]})
            for s in spans:
                sizes.append(round(s.get("size", 0.0), 2))
                if not have_color:
                    first_color = s.get("color", 0)
                    have_color = True
        text = _join_lines(block_lines, block["bbox"])
        if not text.strip():
            continue
        size = Counter(sizes).most_common(1)[0][0] if sizes else 10.0
        skip = looks_untranslatable(text)
        blocks.append({
            "id": f"p{pno}_b{bidx}",
            "bbox": [round(c, 2) for c in block["bbox"]],
            "text": text,
            "size": size,
            "color": first_color,
            "skip": skip,
            "skip_reason": "non-prose" if skip else None,
        })
        bidx += 1
    return {
        "page": pno,
        "width": round(page.rect.width, 2),
        "height": round(page.rect.height, 2),
        "blocks": blocks,
    }


def extract_document(pdf_path, *, source_lang="en", target_lang="no", pages=None):
    """Return the blocks.json contract dict. `pages` = set of 0-based indices or None."""
    doc = fitz.open(pdf_path)
    try:
        page_count = doc.page_count
        out_pages = []
        for pno in range(page_count):
            if pages is not None and pno not in pages:
                continue
            out_pages.append(_extract_page(doc.load_page(pno), pno))
    finally:
        doc.close()
    return {
        "source_pdf": Path(pdf_path).name,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "page_count": page_count,
        "pages": out_pages,
    }


def run(pdf_path, out_path, *, source_lang="en", target_lang="no", pages=None):
    doc = extract_document(pdf_path, source_lang=source_lang, target_lang=target_lang, pages=pages)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc
