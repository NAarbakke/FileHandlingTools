"""Convert a born-digital PDF to Markdown (pymupdf4llm)."""
from __future__ import annotations

import pymupdf4llm

from convert import common


def pdf_to_md(in_path):
    return pymupdf4llm.to_markdown(str(in_path))


if __name__ == "__main__":
    common.cli(pdf_to_md, in_suffixes={".pdf"}, out_suffix=".md", description=__doc__)
