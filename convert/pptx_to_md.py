"""Convert a PowerPoint .pptx file to Markdown (markitdown)."""
from __future__ import annotations

from convert import common


def pptx_to_md(in_path):
    return common.markitdown_to_md(in_path)


if __name__ == "__main__":
    common.cli(pptx_to_md, in_suffixes={".pptx"}, out_suffix=".md", description=__doc__)
