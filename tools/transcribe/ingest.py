"""Stage 1: normalize any input (image or PDF) into one PNG per page.

A PDF has each page rasterized at `dpi` (PyMuPDF `fitz.Matrix`, same approach as
translate's QA renderer). A standalone image is loaded directly. Optional
grayscale conversion can help the VLM on noisy scans.
"""
from __future__ import annotations

import json
from pathlib import Path

import fitz

IMAGE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp", ".pnm", ".ppm",
}


def _save_pixmap(pix, gray, path):
    if gray and (pix.colorspace is None or pix.colorspace.n > 1):
        pix = fitz.Pixmap(fitz.csGRAY, pix)
    pix.save(str(path))


def ingest(input_path, out_dir, *, dpi=200, gray=False, pages=None):
    """Rasterize `input_path` to one PNG per page in `out_dir`.

    `pages` is an optional set of 0-based page indices to keep (PDF only).
    Returns a manifest dict: {source, dpi, page_count, pages:[{page, image}]},
    where `page` is the 1-based source page number.
    """
    src = Path(input_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    entries = []

    if src.suffix.lower() in IMAGE_SUFFIXES:
        dst = out / "page_001.png"
        _save_pixmap(fitz.Pixmap(str(src)), gray, dst)
        entries.append({"page": 1, "image": str(dst)})
    else:
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        doc = fitz.open(str(src))
        try:
            for pno in range(doc.page_count):
                if pages is not None and pno not in pages:
                    continue
                pix = doc.load_page(pno).get_pixmap(matrix=mat)
                dst = out / f"page_{pno + 1:03d}.png"
                _save_pixmap(pix, gray, dst)
                entries.append({"page": pno + 1, "image": str(dst)})
        finally:
            doc.close()

    return {"source": src.name, "dpi": dpi, "page_count": len(entries), "pages": entries}


def run(input_path, manifest_path, out_dir, *, dpi=200, gray=False, pages=None):
    """Run ingest and persist the manifest JSON (pipeline checkpoint)."""
    manifest = ingest(input_path, out_dir, dpi=dpi, gray=gray, pages=pages)
    mp = Path(manifest_path)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
