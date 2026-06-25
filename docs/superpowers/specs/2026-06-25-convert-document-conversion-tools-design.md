# Design: `convert/` — one-shot document→text conversions

Date: 2026-06-25
Status: Approved (pending spec review)

## Purpose & boundary

A set of **deterministic, offline, no-model** scripts that convert a single
document into LLM-friendly text. This is the *cheap extraction path*: it reads a
document's existing content and writes it out as Markdown or plain text so the
result can be fed to an LLM for meaning-extraction (summaries, Q&A, RAG).

Scope boundary:

- **Born-digital only.** PDF scripts extract the existing text layer. Scanned /
  image-only PDFs (no text layer) are **not** handled here — that remains the job
  of the existing `transcribe` tool (VLM/OCR).
- **No Ollama, no network, no model calls.** Conversions are deterministic and
  run fully offline, unlike `translate`/`transcribe`.
- Only the four requested conversions are in scope: pdf→md, pdf→txt, docx→md,
  pptx→md.

## Tool selection (rationale)

No single library is best at every format, so the design uses a deliberate mix
("hybrid best-of-breed"):

| Conversion | Tool | Why |
|------------|------|-----|
| pdf → md   | `pymupdf4llm` | Purpose-built for LLM-ready Markdown from PDFs (preserves headings, lists, tables, reading order). Built on PyMuPDF, which is already a dependency. |
| pdf → txt  | PyMuPDF (`fitz`) `page.get_text()` | Already a dependency; deterministic plain-text extraction with no new code of consequence. |
| docx → md  | `markitdown` | Microsoft's document→Markdown tool, built for LLM consumption; uses `mammoth` under the hood to map Word styles to Markdown. |
| pptx → md  | `markitdown` | Same tool; walks slides + notes via `python-pptx`. One dependency cleanly covers both Office formats with no custom slide-walking code. |

`officecli` was considered and rejected: it is an authoring/analysis/proofreading
CLI, not a library suited to batch programmatic conversion.

## Files

```
convert/
  __init__.py        package marker (so tests/tui import `convert.*` like core/translate)
  common.py          shared CLI runner + IO helpers + the markitdown wrapper
  pdf_to_md.py       PDF  -> Markdown   (pymupdf4llm)
  pdf_to_txt.py      PDF  -> plain text (PyMuPDF get_text)
  docx_to_md.py      DOCX -> Markdown   (markitdown)
  pptx_to_md.py      PPTX -> Markdown   (markitdown)
```

## The testable seam

Mirrors the repo's existing convention (one `pipeline()` function that both
`tui.py` and the tests call). Each script exposes **one pure function**
`name(in_path) -> str` that returns the converted text — no argv parsing, no file
writes — so tests call it directly. `common.cli(...)` wraps that pure function for
command-line use.

Example (`pdf_to_md.py`):

```python
"""Convert a born-digital PDF to Markdown (pymupdf4llm)."""
import pymupdf4llm
from convert import common

def pdf_to_md(in_path):
    return pymupdf4llm.to_markdown(str(in_path))

if __name__ == "__main__":
    common.cli(pdf_to_md, in_suffixes={".pdf"}, out_suffix=".md", description=__doc__)
```

- `pdf_to_txt.py`: `"\n\n".join(page.get_text() for page in fitz.open(str(in_path)))`
  (document closed in a `finally`, matching `translate/extract.py`).
- `docx_to_md.py` / `pptx_to_md.py`: both delegate to a shared
  `common.markitdown_to_md(in_path)`. They differ only in accepted suffix and
  entrypoint description. The real logic lives once in `common.py`; the scripts
  are typed entrypoints — this is what honors "one script per process" without
  duplicating the markitdown call.

## `common.py` responsibilities

- `cli(convert_fn, *, in_suffixes, out_suffix, description)`: argparse over
  `sys.argv`. Accepts **one or more** input paths (serves the "a bunch of PDFs"
  goal). Optional `-o/--out`, allowed only when exactly one input is given
  (error otherwise). Validates each input exists and has an allowed suffix, calls
  `convert_fn`, writes each result, prints what it wrote, exits non-zero on error.
- Default output path: **sibling of the input**, same stem, new suffix
  (`report.pdf` → `report.md`). `-o` overrides (single-input only).
- `markitdown_to_md(in_path)`: `MarkItDown().convert(str(in_path)).text_content`.
- Output is written UTF-8 with `mkdir(parents=True, exist_ok=True)` on the parent.

## TUI integration

Add `run_convert(input_fn, output_fn)` following the existing
`run_<tool>(input_fn, output_fn)` pattern:

1. Ask for the input path.
2. Infer source type from the suffix. If `.pdf`, ask target format `md`/`txt`
   (default `md`). `.docx`/`.pptx` → `md`.
3. Dispatch to the matching pure function, write the sibling output file, report
   the path via `output_fn`.

Register in `TOOLS`:

```python
{"key": "3", "label": "convert", "desc": "pdf/docx/pptx -> md/txt", "run": run_convert}
```

The existing per-tool `try/except` in `tui.run()` keeps the menu alive if a
conversion raises.

## Tests

Mirror the repo's `tests/conftest.py` convention of building tiny fixtures
programmatically (no binary blobs checked in):

- PDF fixture via PyMuPDF, DOCX fixture via `python-docx` (already a dep), PPTX
  fixture via `python-pptx`.
- Assert each conversion function returns expected substrings from its fixture.
- `common.py` tests: suffix rejection, default output-path resolution, multi-input
  handling, and the `-o`-with-multiple-inputs error.

All tests run with **no model and no network** — both `pymupdf4llm` and
`markitdown` are local, deterministic libraries — consistent with the project
rule that "the suite never touches a live model."

## Dependencies (`pyproject.toml`)

- Runtime: add `pymupdf4llm` and `markitdown` (with whatever extra enables the
  docx + pptx converters; exact extra verified at implementation and pinned via
  `uv.lock`).
- Dev: add `python-pptx` to build the PPTX test fixture (markitdown pulls it
  transitively, but it is declared explicitly so fixtures don't rely on a
  transitive dep).

## Error handling

- Missing input file → clear message + exit 1.
- Wrong suffix → message listing accepted suffixes + exit 1.
- Library failure → wrapped as `failed to convert <path>: <err>` to stderr +
  exit 1.
- TUI already catches per-tool exceptions, so the menu survives a failed
  conversion.

## Non-goals (YAGNI for v1)

- No OCR / scanned-PDF handling (→ `transcribe`).
- No page-range selection (easy to add later via `core.pages.parse_pages`).
- No other formats (xlsx, html, images).
- No stdout streaming (always writes a file).
