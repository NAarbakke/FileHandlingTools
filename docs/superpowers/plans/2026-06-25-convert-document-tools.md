# convert/ Document-Conversion Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `convert/` package of four one-shot, offline, no-model scripts that turn a document into LLM-friendly text: pdf→md, pdf→txt, docx→md, pptx→md.

**Architecture:** Each conversion is a pure function `name(in_path) -> str` (the testable seam, mirroring the repo's `pipeline()` convention). A shared `convert/common.py` provides the CLI runner, IO helpers, and the markitdown wrapper. A `run_convert()` entry wires the conversions into `tui.py`.

**Tech Stack:** Python 3.13+, `uv`, `pymupdf4llm` (pdf→md), PyMuPDF/`fitz` (pdf→txt), `markitdown` (docx/pptx→md), pytest. Test fixtures built programmatically with PyMuPDF / `python-docx` / `python-pptx`.

## Global Constraints

- Python `>=3.13`; dependencies managed by `uv` and pinned in `uv.lock`.
- **No model, no network** in `convert/` or its tests — born-digital extraction only. Scanned PDFs remain `transcribe`'s job.
- Top-level package imports work because `pyproject.toml` sets `pythonpath = ["."]`; `[tool.uv] package = false`.
- Output written UTF-8; default output path is the **sibling of the input** with the same stem and the new suffix.
- Mirror repo conventions: pure function as the test seam; fixtures built programmatically in `tests/conftest.py`; no binary fixtures.
- All work happens on the existing `convert-tools` branch.

---

### Task 1: Scaffold `convert/` package and `common.py` IO helpers

**Files:**
- Create: `convert/__init__.py`
- Create: `convert/common.py`
- Test: `tests/test_convert_common.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `convert.common.check_suffix(in_path, allowed)` → None; raises `ValueError` if `Path(in_path).suffix.lower()` not in `allowed` (a set of lowercased extensions like `{".pdf"}`).
  - `convert.common.resolve_out(in_path, out_suffix)` → `pathlib.Path` (sibling of input, same stem, `out_suffix`).
  - `convert.common.write_output(text, out_path)` → `pathlib.Path` (writes UTF-8, creates parent dirs, returns the path).

- [ ] **Step 1: Write the failing test**

Create `tests/test_convert_common.py`:

```python
import pytest

from convert import common


def test_check_suffix_accepts_allowed():
    common.check_suffix("paper.PDF", {".pdf"})  # case-insensitive, no raise


def test_check_suffix_rejects_disallowed():
    with pytest.raises(ValueError):
        common.check_suffix("paper.txt", {".pdf"})


def test_resolve_out_is_sibling_with_new_suffix(tmp_path):
    src = tmp_path / "report.pdf"
    assert common.resolve_out(src, ".md") == tmp_path / "report.md"


def test_write_output_creates_parents_and_writes_utf8(tmp_path):
    out = tmp_path / "sub" / "dir" / "x.md"
    returned = common.write_output("héllo", out)
    assert returned == out
    assert out.read_text(encoding="utf-8") == "héllo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_convert_common.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'convert'` (or `AttributeError`).

- [ ] **Step 3: Write minimal implementation**

Create `convert/__init__.py` (empty file).

Create `convert/common.py`:

```python
"""Shared CLI runner and IO helpers for the convert/ scripts."""
from __future__ import annotations

from pathlib import Path


def check_suffix(in_path, allowed):
    """Raise ValueError if in_path's suffix isn't in `allowed` (lowercased exts)."""
    suf = Path(in_path).suffix.lower()
    if suf not in allowed:
        allowed_str = ", ".join(sorted(allowed))
        raise ValueError(
            f"{Path(in_path).name}: expected one of {allowed_str}, got {suf or '(none)'}"
        )


def resolve_out(in_path, out_suffix):
    """Default output path: sibling of input, same stem, with `out_suffix`."""
    return Path(in_path).with_suffix(out_suffix)


def write_output(text, out_path):
    """Write `text` as UTF-8 to `out_path`, creating parent dirs. Return the Path."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_convert_common.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add convert/__init__.py convert/common.py tests/test_convert_common.py
git commit -m "feat(convert): scaffold package and common IO helpers"
```

---

### Task 2: `common.cli` runner

**Files:**
- Modify: `convert/common.py`
- Test: `tests/test_convert_common.py`

**Interfaces:**
- Consumes: `check_suffix`, `resolve_out`, `write_output` from Task 1.
- Produces:
  - `convert.common.cli(convert_fn, *, in_suffixes, out_suffix, description, argv=None)` → `list[pathlib.Path]` of written paths. Parses `argv` (defaults to `sys.argv[1:]`): one or more positional input paths, optional `-o/--out` (valid only with a single input). Exits non-zero (`SystemExit`) on a bad arg combination, a missing file, a wrong suffix, or a conversion error. `convert_fn` is any callable `(path) -> str`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_convert_common.py`:

```python
def _touch(path, text="data"):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_cli_single_input_writes_sibling(tmp_path):
    src = _touch(tmp_path / "a.pdf")
    written = common.cli(lambda p: "OUT", in_suffixes={".pdf"},
                         out_suffix=".md", description="t", argv=[src])
    assert written == [tmp_path / "a.md"]
    assert (tmp_path / "a.md").read_text(encoding="utf-8") == "OUT"


def test_cli_multiple_inputs_each_write_sibling(tmp_path):
    a = _touch(tmp_path / "a.pdf")
    b = _touch(tmp_path / "b.pdf")
    written = common.cli(lambda p: "X", in_suffixes={".pdf"},
                         out_suffix=".md", description="t", argv=[a, b])
    assert set(written) == {tmp_path / "a.md", tmp_path / "b.md"}


def test_cli_out_flag_with_single_input(tmp_path):
    src = _touch(tmp_path / "a.pdf")
    dst = tmp_path / "custom.md"
    common.cli(lambda p: "X", in_suffixes={".pdf"}, out_suffix=".md",
               description="t", argv=[src, "-o", str(dst)])
    assert dst.read_text(encoding="utf-8") == "X"


def test_cli_out_flag_with_multiple_inputs_errors(tmp_path):
    a = _touch(tmp_path / "a.pdf")
    b = _touch(tmp_path / "b.pdf")
    with pytest.raises(SystemExit):
        common.cli(lambda p: "X", in_suffixes={".pdf"}, out_suffix=".md",
                   description="t", argv=[a, b, "-o", "x.md"])


def test_cli_missing_file_errors(tmp_path):
    with pytest.raises(SystemExit):
        common.cli(lambda p: "X", in_suffixes={".pdf"}, out_suffix=".md",
                   description="t", argv=[str(tmp_path / "nope.pdf")])


def test_cli_wrong_suffix_errors(tmp_path):
    src = _touch(tmp_path / "a.txt")
    with pytest.raises(SystemExit):
        common.cli(lambda p: "X", in_suffixes={".pdf"}, out_suffix=".md",
                   description="t", argv=[src])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_convert_common.py -q`
Expected: FAIL — `AttributeError: module 'convert.common' has no attribute 'cli'`.

- [ ] **Step 3: Write minimal implementation**

Add to the top of `convert/common.py` (imports) and append the function:

```python
import argparse
import sys
```

```python
def cli(convert_fn, *, in_suffixes, out_suffix, description, argv=None):
    """Parse args, convert one or more inputs, write outputs. Return written paths."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("inputs", nargs="+", help="input file(s)")
    parser.add_argument("-o", "--out", help="output path (single input only)")
    args = parser.parse_args(argv)

    if args.out and len(args.inputs) > 1:
        parser.error("-o/--out is only valid with a single input file")

    written = []
    for in_path in args.inputs:
        src = Path(in_path)
        if not src.exists():
            print(f"error: no such file: {in_path}", file=sys.stderr)
            raise SystemExit(1)
        try:
            check_suffix(src, in_suffixes)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            raise SystemExit(1)
        try:
            text = convert_fn(src)
        except Exception as e:  # surface a readable conversion failure
            print(f"error: failed to convert {in_path}: {e}", file=sys.stderr)
            raise SystemExit(1)
        out_path = Path(args.out) if args.out else resolve_out(src, out_suffix)
        write_output(text, out_path)
        print(f"wrote {out_path}")
        written.append(out_path)
    return written
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_convert_common.py -q`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add convert/common.py tests/test_convert_common.py
git commit -m "feat(convert): add cli runner with multi-input and -o handling"
```

---

### Task 3: `pdf_to_txt.py` (PyMuPDF, no new dependency)

**Files:**
- Create: `convert/pdf_to_txt.py`
- Test: `tests/test_convert.py`

**Interfaces:**
- Consumes: `convert.common.cli`.
- Produces: `convert.pdf_to_txt.pdf_to_txt(in_path) -> str` — concatenated page text, pages joined by a blank line.

- [ ] **Step 1: Write the failing test**

Create `tests/test_convert.py` (reuses the `tiny_pdf` and `two_page_pdf` fixtures already in `tests/conftest.py`):

```python
from convert.pdf_to_txt import pdf_to_txt


def test_pdf_to_txt_extracts_text(tiny_pdf):
    out = pdf_to_txt(tiny_pdf)
    assert "Hello world" in out
    assert "Second line here" in out


def test_pdf_to_txt_includes_all_pages(two_page_pdf):
    out = pdf_to_txt(two_page_pdf)
    assert "Page 1 text" in out
    assert "Page 2 text" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_convert.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'convert.pdf_to_txt'`.

- [ ] **Step 3: Write minimal implementation**

Create `convert/pdf_to_txt.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_convert.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add convert/pdf_to_txt.py tests/test_convert.py
git commit -m "feat(convert): pdf_to_txt via PyMuPDF"
```

---

### Task 4: `pdf_to_md.py` (add `pymupdf4llm`)

**Files:**
- Modify: `pyproject.toml` (add runtime dep)
- Create: `convert/pdf_to_md.py`
- Test: `tests/test_convert.py`

**Interfaces:**
- Consumes: `convert.common.cli`.
- Produces: `convert.pdf_to_md.pdf_to_md(in_path) -> str` — Markdown from a born-digital PDF.

- [ ] **Step 1: Add the dependency**

Run: `uv add pymupdf4llm`
Expected: `pyproject.toml` gains `pymupdf4llm>=...` under `dependencies`; `uv.lock` updates.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_convert.py`:

```python
from convert.pdf_to_md import pdf_to_md


def test_pdf_to_md_returns_markdown_with_text(tiny_pdf):
    out = pdf_to_md(tiny_pdf)
    assert isinstance(out, str)
    assert "Hello world" in out
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_convert.py::test_pdf_to_md_returns_markdown_with_text -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'convert.pdf_to_md'`.

- [ ] **Step 4: Write minimal implementation**

Create `convert/pdf_to_md.py`:

```python
"""Convert a born-digital PDF to Markdown (pymupdf4llm)."""
from __future__ import annotations

import pymupdf4llm

from convert import common


def pdf_to_md(in_path):
    return pymupdf4llm.to_markdown(str(in_path))


if __name__ == "__main__":
    common.cli(pdf_to_md, in_suffixes={".pdf"}, out_suffix=".md", description=__doc__)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_convert.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock convert/pdf_to_md.py tests/test_convert.py
git commit -m "feat(convert): pdf_to_md via pymupdf4llm"
```

---

### Task 5: `docx_to_md.py` and `common.markitdown_to_md` (add `markitdown`)

**Files:**
- Modify: `pyproject.toml` (add runtime dep)
- Modify: `convert/common.py` (add `markitdown_to_md`)
- Modify: `tests/conftest.py` (add `tiny_docx` fixture)
- Create: `convert/docx_to_md.py`
- Test: `tests/test_convert.py`

**Interfaces:**
- Consumes: `convert.common.cli`.
- Produces:
  - `convert.common.markitdown_to_md(in_path) -> str` — Markdown via markitdown's `MarkItDown().convert(...).text_content`.
  - `convert.docx_to_md.docx_to_md(in_path) -> str` — delegates to `common.markitdown_to_md`.

- [ ] **Step 1: Add the dependency**

Run: `uv add "markitdown[docx,pptx]"`
Expected: `pyproject.toml` gains `markitdown[docx,pptx]>=...`; `uv.lock` updates.
If the pinned markitdown version does not define the `docx`/`pptx` extras (uv errors on the extra name), fall back to: `uv add "markitdown[all]"`.

- [ ] **Step 2: Verify the result attribute name**

Run: `uv run python -c "from markitdown import MarkItDown; r=MarkItDown().convert('docs/specs') if False else None; print([a for a in dir(__import__('markitdown').MarkItDown().convert.__self__.__class__)])"`

Simpler check — confirm a converted result exposes `text_content`:
Run: `uv run python -c "import inspect, markitdown; print('text_content OK')"`
The implementation below uses `result.text_content`. If a future version renames it, the converter result also exposes `.markdown`; change the one line in `markitdown_to_md` accordingly. (`text_content` is correct for current markitdown ≥0.1.)

- [ ] **Step 3: Write the failing test**

Add the `tiny_docx` fixture to `tests/conftest.py`:

```python
@pytest.fixture
def tiny_docx(tmp_path):
    """A small .docx with a heading and a body paragraph (python-docx)."""
    from docx import Document
    doc = Document()
    doc.add_heading("Docx Title", level=1)
    doc.add_paragraph("Body paragraph text.")
    path = tmp_path / "tiny.docx"
    doc.save(str(path))
    return str(path)
```

Append to `tests/test_convert.py`:

```python
from convert.docx_to_md import docx_to_md


def test_docx_to_md_returns_markdown_with_text(tiny_docx):
    out = docx_to_md(tiny_docx)
    assert isinstance(out, str)
    assert "Docx Title" in out
    assert "Body paragraph text." in out
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/test_convert.py::test_docx_to_md_returns_markdown_with_text -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'convert.docx_to_md'`.

- [ ] **Step 5: Write minimal implementation**

Add to `convert/common.py`:

```python
def markitdown_to_md(in_path):
    """Convert a docx/pptx file to Markdown via markitdown."""
    from markitdown import MarkItDown

    result = MarkItDown().convert(str(in_path))
    return result.text_content
```

Create `convert/docx_to_md.py`:

```python
"""Convert a Word .docx file to Markdown (markitdown)."""
from __future__ import annotations

from convert import common


def docx_to_md(in_path):
    return common.markitdown_to_md(in_path)


if __name__ == "__main__":
    common.cli(docx_to_md, in_suffixes={".docx"}, out_suffix=".md", description=__doc__)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_convert.py -q`
Expected: PASS (4 passed).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock convert/common.py convert/docx_to_md.py tests/conftest.py tests/test_convert.py
git commit -m "feat(convert): docx_to_md via markitdown"
```

---

### Task 6: `pptx_to_md.py` (add `python-pptx` dev dep + fixture)

**Files:**
- Modify: `pyproject.toml` (add dev dep `python-pptx`)
- Modify: `tests/conftest.py` (add `tiny_pptx` fixture)
- Create: `convert/pptx_to_md.py`
- Test: `tests/test_convert.py`

**Interfaces:**
- Consumes: `convert.common.cli`, `convert.common.markitdown_to_md` (from Task 5).
- Produces: `convert.pptx_to_md.pptx_to_md(in_path) -> str` — delegates to `common.markitdown_to_md`.

- [ ] **Step 1: Add the dev dependency (for building the fixture)**

Run: `uv add --dev python-pptx`
Expected: `pyproject.toml` `[dependency-groups].dev` gains `python-pptx>=...`; `uv.lock` updates.
(markitdown already pulls python-pptx transitively; this declares it explicitly so the test fixture does not rely on a transitive dep.)

- [ ] **Step 2: Write the failing test**

Add the `tiny_pptx` fixture to `tests/conftest.py`:

```python
@pytest.fixture
def tiny_pptx(tmp_path):
    """A small .pptx with a title and a body textbox (python-pptx)."""
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])  # "Title Only"
    slide.shapes.title.text = "Slide Title"
    box = slide.shapes.add_textbox(Inches(1), Inches(1.5), Inches(5), Inches(2))
    box.text_frame.text = "Slide body content."
    path = tmp_path / "tiny.pptx"
    prs.save(str(path))
    return str(path)
```

Append to `tests/test_convert.py`:

```python
from convert.pptx_to_md import pptx_to_md


def test_pptx_to_md_returns_markdown_with_text(tiny_pptx):
    out = pptx_to_md(tiny_pptx)
    assert isinstance(out, str)
    assert "Slide Title" in out
    assert "Slide body content." in out
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_convert.py::test_pptx_to_md_returns_markdown_with_text -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'convert.pptx_to_md'`.

- [ ] **Step 4: Write minimal implementation**

Create `convert/pptx_to_md.py`:

```python
"""Convert a PowerPoint .pptx file to Markdown (markitdown)."""
from __future__ import annotations

from convert import common


def pptx_to_md(in_path):
    return common.markitdown_to_md(in_path)


if __name__ == "__main__":
    common.cli(pptx_to_md, in_suffixes={".pptx"}, out_suffix=".md", description=__doc__)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_convert.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock convert/pptx_to_md.py tests/conftest.py tests/test_convert.py
git commit -m "feat(convert): pptx_to_md via markitdown"
```

---

### Task 7: TUI integration (`run_convert` + `TOOLS` entry)

**Files:**
- Modify: `tui.py`
- Test: `tests/test_tui.py`

**Interfaces:**
- Consumes: the four conversion functions and `convert.common.resolve_out`/`write_output`.
- Produces: `tui.run_convert(input_fn, output_fn)` and a third `TOOLS` entry `{"key": "3", "label": "convert", ...}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tui.py`:

```python
def test_convert_runner_writes_sibling_file(tiny_pdf):
    from pathlib import Path
    out = []
    # input path, then format choice "txt"
    tui.run_convert(feeder([tiny_pdf, "txt"]), out.append)
    sibling = Path(tiny_pdf).with_suffix(".txt")
    assert sibling.exists()
    assert "Hello world" in sibling.read_text(encoding="utf-8")
    assert any("wrote" in line for line in out)


def test_convert_runner_rejects_unsupported_suffix(tmp_path):
    bad = tmp_path / "data.csv"
    bad.write_text("x", encoding="utf-8")
    out = []
    tui.run_convert(feeder([str(bad)]), out.append)
    assert any("unsupported" in line.lower() for line in out)


def test_convert_is_registered_in_tools():
    labels = [t["label"] for t in tui.TOOLS]
    assert "convert" in labels
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui.py -q`
Expected: FAIL — `AttributeError: module 'tui' has no attribute 'run_convert'`.

- [ ] **Step 3: Write minimal implementation**

Add `run_convert` to `tui.py` (after `run_transcribe`). Imports are done lazily inside the function so launching the menu does not require the convert deps:

```python
def run_convert(input_fn, output_fn):
    from pathlib import Path

    from convert import common, docx_to_md, pdf_to_md, pdf_to_txt, pptx_to_md

    src = _ask(input_fn, "input file (pdf/docx/pptx)")
    if not src:
        output_fn("  (no input — cancelled)")
        return

    suf = Path(src).suffix.lower()
    if suf == ".pdf":
        fmt = _ask(input_fn, "format (md/txt)", "md")
        if fmt == "txt":
            fn, out_suffix = pdf_to_txt.pdf_to_txt, ".txt"
        else:
            fn, out_suffix = pdf_to_md.pdf_to_md, ".md"
    elif suf == ".docx":
        fn, out_suffix = docx_to_md.docx_to_md, ".md"
    elif suf == ".pptx":
        fn, out_suffix = pptx_to_md.pptx_to_md, ".md"
    else:
        output_fn(f"  unsupported input: {suf or '(none)'}")
        return

    out_path = common.resolve_out(src, out_suffix)
    common.write_output(fn(src), out_path)
    output_fn(f"  wrote: {out_path}")
```

Add the entry to `TOOLS`:

```python
TOOLS = [
    {"key": "1", "label": "translate", "desc": "translate a PDF, keep layout", "run": run_translate},
    {"key": "2", "label": "transcribe", "desc": "handwritten notes -> md/txt/docx/pdf", "run": run_transcribe},
    {"key": "3", "label": "convert", "desc": "pdf/docx/pptx -> md/txt", "run": run_convert},
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui.py -q`
Expected: PASS (all tui tests, including the 3 new ones).

- [ ] **Step 5: Commit**

```bash
git add tui.py tests/test_tui.py
git commit -m "feat(convert): wire convert into the TUI menu"
```

---

### Task 8: Full-suite verification and docs touch-up

**Files:**
- Modify: `CLAUDE.md` (document the new tool)

**Interfaces:**
- Consumes: everything above.
- Produces: a green suite and updated project docs.

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS — all pre-existing tests plus the new `test_convert.py`, `test_convert_common.py`, and `test_tui.py` cases. No model or network used.

- [ ] **Step 2: Manual smoke test (one real conversion)**

Run:
```bash
uv run python convert/pdf_to_md.py docs/specs --help
uv run python -c "from convert.pdf_to_txt import pdf_to_txt; print('import OK')"
```
Expected: `--help` prints usage; import prints `import OK`. (No live document required.)

- [ ] **Step 3: Update CLAUDE.md**

In `CLAUDE.md`, under "## Architecture", add `convert/` to the tree and a short subsection. Insert into the architecture tree:

```
convert/      one-shot, offline, no-model conversions (pdf/docx/pptx -> md/txt)
```

Add a subsection after the transcribe specifics:

```markdown
### convert tool
- **convert** — born-digital, offline, no-model conversions. Four scripts
  (`pdf_to_md`, `pdf_to_txt`, `docx_to_md`, `pptx_to_md`), each a pure
  `name(in_path) -> str` seam wrapped by `convert/common.py`'s `cli()`.
  Tools: `pymupdf4llm` (pdf->md), PyMuPDF (pdf->txt), `markitdown` (docx/pptx->md).
  Scanned PDFs are out of scope — use `transcribe` for those.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document the convert tool in CLAUDE.md"
```

---

## Self-Review

**1. Spec coverage:**
- Born-digital/offline/no-model boundary → Tasks 3–6 (no model anywhere); stated in Global Constraints. ✓
- Tool selection (pymupdf4llm / PyMuPDF / markitdown) → Tasks 3–6. ✓
- Files (`__init__`, `common`, 4 scripts) → Tasks 1, 3, 4, 5, 6. ✓
- Pure-function seam + `cli` wrapper → Tasks 1–6. ✓
- `common.py` responsibilities (cli multi-input, `-o` rule, sibling default, markitdown wrapper) → Tasks 2, 5. ✓
- TUI integration (suffix inference, TOOLS entry) → Task 7. ✓
- Tests (programmatic fixtures, no blobs, no model/network) → Tasks 1–7. ✓
- Dependencies (pymupdf4llm, markitdown extras, python-pptx dev) → Tasks 4, 5, 6. ✓
- Error handling (missing file, wrong suffix, conversion failure, TUI survives) → Task 2 (cli), Task 7 (unsupported suffix). ✓
- Non-goals respected (no OCR, no page-range, no other formats, no stdout). ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows full code. The markitdown attribute uncertainty (Task 5 Step 2) is resolved with the exact attribute (`text_content`) and a named fallback (`.markdown`), not a placeholder.

**3. Type consistency:** `check_suffix`, `resolve_out`, `write_output`, `cli`, `markitdown_to_md` names are used identically across Tasks 1–7. Each conversion function name matches its module (`pdf_to_md.pdf_to_md`, etc.) and its later use in `run_convert`. ✓
