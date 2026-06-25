"""Integration tests for the convert/ scripts on real documents.

Unlike test_convert_common.py / test_<fmt>.py (which use tiny generated fixtures),
these run the converters against the real files in tests/test_docs/ and compare
the result to committed golden outputs in tests/test_docs/expected/. They use no
model and no network (markitdown / pymupdf4llm are local libraries).

Speed: the markitdown (docx/pptx) and pymupdf4llm (pdf->md) paths pull heavy ML
dependencies (onnxruntime); on a real document they take seconds to tens of
seconds, which would wreck the fast default suite. Those tests are gated behind
the CONVERT_SLOW_TESTS env var. The PyMuPDF-only paths (pdf->txt) and the CLI
entry-point guard run by default. Run the full set with:

    CONVERT_SLOW_TESTS=1 uv run pytest tests/test_convert_integration.py -q

Regenerating the goldens (after a deliberate dependency bump that changes output):

    uv run python -m tools.convert.docx_to_md  tests/test_docs/report.docx               -o tests/test_docs/expected/report.md
    uv run python -m tools.convert.pptx_to_md  tests/test_docs/deck.pptx                 -o tests/test_docs/expected/deck.md
    uv run python -m tools.convert.pdf_to_txt  tests/test_docs/translation-test-doc.pdf  -o tests/test_docs/expected/translation-test-doc.txt
    uv run python -m tools.convert.pdf_to_txt  tests/test_docs/handwritten-test-doc.pdf  -o tests/test_docs/expected/handwritten-test-doc.txt
    uv run python -m tools.convert.pdf_to_md   tests/test_docs/translation-test-doc.pdf  -o tests/test_docs/expected/translation-test-doc.md
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = Path(__file__).parent / "test_docs"
EXPECTED = DOCS / "expected"

# Heavy ML-dependency conversions (markitdown / pymupdf4llm) — opt-in only.
slow = pytest.mark.skipif(
    not os.environ.get("CONVERT_SLOW_TESTS"),
    reason="heavy ML conversion (markitdown/pymupdf4llm); set CONVERT_SLOW_TESTS=1",
)


def _norm(s):
    """Normalize newlines so the comparison is OS-independent (Windows CRLF)."""
    return s.replace("\r\n", "\n")


def _golden(name):
    return _norm((EXPECTED / name).read_text(encoding="utf-8"))


# --- fast (PyMuPDF only, no ML deps) — run by default --------------------------

def test_pdf_to_txt_matches_golden():
    from tools.convert.pdf_to_txt import pdf_to_txt

    out = _norm(pdf_to_txt(str(DOCS / "translation-test-doc.pdf")))
    assert out == _golden("translation-test-doc.txt")
    assert "Fluidic Thrust Vectoring" in out


def test_pdf_to_txt_scanned_is_sparse():
    """A scanned/handwritten PDF has no real text layer -> near-empty extraction.

    Documents the born-digital limitation: scans are transcribe's job, not convert's.
    """
    from tools.convert.pdf_to_txt import pdf_to_txt

    out = _norm(pdf_to_txt(str(DOCS / "handwritten-test-doc.pdf")))
    assert out == _golden("handwritten-test-doc.txt")
    assert len(out) < 1000  # essentially no extractable text


def test_cli_entrypoint_runs_via_module(tmp_path):
    """Guard the documented `python -m tools.convert.<name>` invocation end-to-end.

    Regression test for the import bug: running a script by file path put the
    package dir (not the repo root) on sys.path, breaking `from convert import common`.
    Uses pdf_to_txt (PyMuPDF only) so the guard stays fast.
    """
    out = tmp_path / "out.txt"
    result = subprocess.run(
        [sys.executable, "-m", "tools.convert.pdf_to_txt",
         str(DOCS / "handwritten-test-doc.pdf"), "-o", str(out)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()


# --- slow (heavy ML deps) — opt-in via CONVERT_SLOW_TESTS ----------------------

@slow
def test_docx_to_md_matches_golden():
    from tools.convert.docx_to_md import docx_to_md

    out = _norm(docx_to_md(str(DOCS / "report.docx")))
    assert out == _golden("report.md")
    # the real value-add: a Word table rendered as a Markdown table
    assert "| Region | Growth |" in out


@slow
def test_pptx_to_md_matches_golden():
    from tools.convert.pptx_to_md import pptx_to_md

    out = _norm(pptx_to_md(str(DOCS / "deck.pptx")))
    assert out == _golden("deck.md")
    # markitdown captures the slide table and the speaker notes
    assert "| Region | Growth |" in out
    assert "Remember to mention the South region outperformed." in out


@slow
def test_pdf_to_md_matches_golden():
    from tools.convert.pdf_to_md import pdf_to_md

    out = _norm(pdf_to_md(str(DOCS / "translation-test-doc.pdf")))
    assert out == _golden("translation-test-doc.md")
    assert "## **1. Introduction**" in out
