# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Local, offline document tools (`translate`, `transcribe`, `convert`) run from one terminal
menu (`tui.py`). `translate` and `transcribe` share a single Ollama model configuration and
run against a local Ollama server; `convert` is model-free (pure text extraction). Everything
runs on the user's machine — no cloud, no API keys. Python 3.13+, managed with `uv`.

## Commands

```powershell
uv sync                       # create .venv and install runtime + dev deps (pinned by uv.lock)
uv run python tui.py          # run the menu (the app's entry point)
uv run pytest -q              # full test suite (no Ollama needed — model calls are injected)
uv run pytest tests/test_translate.py -k parse_pages   # single test / filter
uv run python -m convert.pdf_to_md report.pdf          # one-shot convert (no Ollama)
```

The suite never touches a live model, so it is the primary feedback loop; you do **not**
need Ollama running to develop or test. Ollama is only needed for a real end-to-end run.

If `uv run <console-script>` (e.g. `uv run pytest`) ever errors with "trampoline failed to
canonicalize script path", the `.venv` shims are stale (usually after the project folder was
renamed/moved). Rebuild them with `uv sync --reinstall`; `uv run python -m pytest` works
regardless since it bypasses the shim.

## Architecture

Three tools, one shared core, one menu. `translate` and `transcribe` are packages
each exposing a single `pipeline()` function that both `tui.py` and the tests call;
`convert` is a set of one-shot scripts (pure `name(in_path) -> str` functions), not a pipeline.

```
tui.py        the menu; to add a tool, write run_<tool>() and append to TOOLS
core/         shared internals (see below)
translate/    extract -> translate -> rebuild -> render_qa
transcribe/   ingest  -> transcribe -> assemble -> render
convert/      one-shot, offline, no-model conversions (pdf/docx/pptx -> md/txt)
```

### `core/` — single source of truth shared by both tools
- `models.json` + `modelmap.get_model(tool, role, default)` — which Ollama model each
  tool/role uses, configured in one place. Resolution: env var
  `OLLAMA_MODEL_<TOOL>_<ROLE>` → `models.json` → the `default` arg. An explicit
  `model=` passed to `pipeline()` overrides everything.
  (Note: some docstrings/comments say "repo-root models.json" — stale; it lives in `core/`.)
- `ollama.chat(model, messages, ...)` — the one raw-HTTP call to `localhost:11434/api/chat`.
  Vision transcription passes base64 PNGs in a message's `images` field.
- `pages.parse_pages("1-5,8")` — shared 1-based-spec → set of 0-based indices.
- `assets/DejaVuSans.ttf` — the single embedded font used when rebuilding PDFs.

### Pipelines are symmetric and file-checkpointed
Both tools follow the identical shape, so changes to one usually have a mirror in the other:

- **Each stage is a module with `run(in_path, out_path, *, ...)`** that reads a JSON
  checkpoint, mutates a `doc`/`manifest` dict, and writes pretty JSON
  (`ensure_ascii=False`, parents `mkdir`'d). Stages chain only through files in `work/`,
  so any stage can re-run independently of the others.
- **Model-calling stages take an injectable callable** (`translator` / `transcriber` /
  `cleaner`). When it's `None`, the stage constructs the Ollama-backed default
  (`OllamaTranslator`, `OllamaTranscriber`). Tests pass a plain `lambda` instead — this
  is how the whole pipeline runs without a server. `pipeline()` forwards these through.
- **On-disk cache**: model stages hash `(model, prompt, input)` → write the result under
  `work/cache/`, so re-running skips model calls for unchanged inputs.

`work/` and `output/` are gitignored scratch dirs, regenerated each run.

### Tool specifics
- **translate** — born-digital PDFs only (no OCR). `extract.py` reflows soft-wrapped lines
  and marks non-prose blocks `skip` (via `common.looks_untranslatable`) so they aren't
  translated. `rebuild.py` redacts original text and inserts the translation into the same
  boxes, leaving figures/vector graphics untouched. All PDF/raster work is PyMuPDF (`fitz`).
- **transcribe** — image or PDF → verbatim Markdown via a local VLM (the prompt forbids
  translating/rewording). Optional `cleanup` pass is formatting-only. `render.py` emits
  md/txt/pdf with stdlib + PyMuPDF; docx uses `python-docx`. No Pillow anywhere.
- **convert** — born-digital, offline, no-model conversions. Four scripts
  (`pdf_to_md`, `pdf_to_txt`, `docx_to_md`, `pptx_to_md`), each a pure
  `name(in_path) -> str` seam wrapped by `convert/common.py`'s `cli()`.
  Tools: `pymupdf4llm` (pdf->md), PyMuPDF (pdf->txt), `markitdown` (docx/pptx->md).
  Scanned PDFs are out of scope — use `transcribe` for those.

## Conventions
- `pyproject.toml` sets `pythonpath = ["."]` so tests import `translate` / `transcribe` /
  `convert` / `core` / `tui` as top-level packages. `[tool.uv] package = false` — this is an
  app, not an installable library.
- Tests build fixtures (tiny PDFs/PNGs) with PyMuPDF in `tests/conftest.py`; no binary
  fixtures except the integration docs in `tests/test_docs/`.
- `tui.py` strips UTF-8 BOMs from stdin (Windows piped-input quirk) and keeps the menu
  alive on per-tool exceptions.
- Dated design/implementation notes live in `docs/specs/` (specs) and `docs/plans/`
  (plans) — one pair per feature (e.g. the original `translate` work and the `convert` tools).
