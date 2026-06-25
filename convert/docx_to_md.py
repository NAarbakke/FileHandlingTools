"""Convert a Word .docx file to Markdown (markitdown)."""
from __future__ import annotations

from convert import common


def docx_to_md(in_path):
    return common.markitdown_to_md(in_path)


if __name__ == "__main__":
    common.cli(docx_to_md, in_suffixes={".docx"}, out_suffix=".md", description=__doc__)
