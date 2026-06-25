"""Convert a Word .docx file to Markdown (mammoth)."""
from __future__ import annotations

import re

import mammoth

from convert import common


def docx_to_md(in_path):
    with open(in_path, "rb") as fh:
        text = mammoth.convert_to_markdown(fh).value
    # mammoth escapes non-Markdown chars (e.g. '.') with a leading backslash;
    # strip those escapes so output is natural prose Markdown.
    text = re.sub(r"\\([^\\])", r"\1", text)
    return text


if __name__ == "__main__":
    common.cli(docx_to_md, in_suffixes={".docx"}, out_suffix=".md", description=__doc__)
