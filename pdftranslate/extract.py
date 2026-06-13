"""Stage 1: extract text blocks (with positions) from a PDF into blocks.json."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

from .common import looks_untranslatable


def _extract_page(page, pno):
    data = page.get_text("dict")
    blocks = []
    bidx = 0
    for block in data.get("blocks", []):
        if block.get("type", 0) != 0:
            continue  # image block — left untouched in the PDF
        lines_text = []
        sizes = []
        first_color = 0
        have_color = False
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            lines_text.append("".join(s.get("text", "") for s in spans))
            for s in spans:
                sizes.append(round(s.get("size", 0.0), 2))
                if not have_color:
                    first_color = s.get("color", 0)
                    have_color = True
        text = " ".join(t for t in lines_text if t)
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
