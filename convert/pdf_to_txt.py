"""Convert a born-digital PDF to plain text (PyMuPDF)."""
from __future__ import annotations

import fitz

from convert import common


def pdf_to_txt(in_path):
    doc = fitz.open(str(in_path))
    try:
        return "\n\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


if __name__ == "__main__":
    common.cli(pdf_to_txt, in_suffixes={".pdf"}, out_suffix=".txt", description=__doc__)
