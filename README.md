# FileHandlingTools

Local, open-source document tools, run from **one terminal menu**. Everything runs on your
machine — no cloud, no API keys. `translate` and `transcribe` share a single Ollama model
configuration; `convert` is fully offline (no model at all).

| Tool | What it does |
|------|--------------|
| **translate**  | translate a born-digital PDF, keeping its original layout and figures |
| **transcribe** | transcribe handwritten notes (photo, scan, or PDF) into md / txt / docx / pdf |
| **convert**    | extract a born-digital PDF / Word / PowerPoint to Markdown or plain text (no model) |

Which model the `translate` / `transcribe` tools use is defined once in
[`core/models.json`](core/models.json) — see [Shared model mapper](#shared-model-mapper).
`convert` calls no model.

## Layout

```
tui.py          entry point (the menu)
core/           shared internals: model mapper (modelmap.py + models.json),
                Ollama client (ollama.py), helpers (pages.py), bundled font
tools/          the three tools, each a package:
  translate/    PDF translate pipeline: extract -> translate -> rebuild -> render_qa
  transcribe/   handwriting pipeline:    ingest  -> transcribe -> assemble -> render
  convert/      offline conversions (no model): pdf/docx/pptx -> md/txt
input/          drop source documents here (gitignored); the menu lists them to pick
output/         generated results (gitignored)
tests/          pytest suite (runs without Ollama; model calls are mocked)
```

`translate` and `transcribe` are packages exposing one `pipeline()` function that the TUI
and tests call. `convert` is a set of small per-format scripts, each a pure
`name(in_path) -> str` function sharing `convert/common.py`.

## Setup

This project uses [uv](https://docs.astral.sh/uv/). One command creates the virtual
environment and installs everything (runtime + dev tools), pinned by `uv.lock`:

```powershell
uv sync
```

Install [Ollama](https://ollama.com) and pull the models you need:

```powershell
ollama pull gemma2:2b      # translate, and the transcribe --cleanup pass (small, low-VRAM/CPU)
ollama pull qwen2.5vl:3b   # transcribe's vision model (needs Ollama >= 0.7.0)
ollama pull moondream      # optional: smaller/faster vision fallback for low-VRAM GPUs
```

## Run — the menu

```powershell
uv run python tui.py
```

Pick a tool by number; it lets you choose a source file from `input/` (or type any
path), asks a few options, runs the pipeline, and writes to `output/`. Choose `0` to quit.

```
FileHandlingTools
=================
 1) translate    translate a PDF, keep layout
 2) transcribe   handwritten notes -> md/txt/docx/pdf
 3) convert      pdf/docx/pptx -> md/txt
 0) quit

Select a tool [1]: 2
  input image/PDF: notes.jpg
  formats [md]: md,docx,pdf
  cleanup pass? [y/N]: n
  ... running ...
  wrote: output/notes.md, output/notes.docx, output/notes.pdf
```

`convert` infers the source type from the file extension. From the menu it lists the files
in `input/` to pick from (or type any path) and writes the result to `output/`:

```
Select a tool [1]: 3
  files in input/:
    1) report.pdf
  input file (pdf/docx/pptx) — number above, or a path [1]: 1
  format (md/txt) [md]: md
  wrote: output/report.md
```

### Scripting (optional)

Each tool is also a plain importable function, so you can drive it from Python:

```python
from tools import translate, transcribe
from tools.convert.pdf_to_md import pdf_to_md

translate.pipeline("paper.pdf", tgt="no")                       # -> output/paper.no.pdf
transcribe.pipeline("notes.jpg", formats=["md", "docx", "pdf"], cleanup=True)
md = pdf_to_md("report.pdf")                                    # returns Markdown as a string
```

---

## translate

Translate a born-digital PDF while keeping its original layout and figures. It reads
each text block with its position, removes only the original text (figures, charts,
photos, and vector graphics are left untouched), translates with a local **Ollama**
model, and inserts the translation back into the same boxes (shrinking the font to fit).

**`translate.pipeline()` options:** `src` (source lang, default `en`), `tgt` (target lang,
default `no`), `model` (default from `models.json`), `pages` (e.g. `"1-5"`),
`skip_translate`, `no_qa`, `out_dir`, `work_dir`. The menu asks for input / target /
source / pages / out-dir.

```
extract   -> work/blocks.json
translate -> work/blocks.<lang>.json   (Ollama + on-disk cache)
rebuild   -> output/<name>.<lang>.pdf  (redact text, keep figures, insert translation)
render_qa -> output/qa/*.png           (original vs translated)
```

**Limitations:** born-digital PDFs only (no OCR for scanned pages); typeface/bold/italic
not reproduced (one embedded DejaVu Sans font); inline equations left as original; assumes
a white page background.

---

## transcribe

Transcribe handwritten notes into a clean digital document. It rasterizes the input
(photo, scan, or PDF), reads each page with a local **vision-language model** via Ollama
(verbatim — it never translates or rewords), and renders to the formats you choose.

> On a 2 GB GPU a 3B VLM is partly offloaded to CPU — it runs, just slower (tens of
> seconds to minutes per page). Pick `moondream` (set `model=` or edit `models.json`) to
> trade some accuracy for speed.

**`transcribe.pipeline()` options:** `formats` (default `["md"]`), `model` (default from
`models.json`), `cleanup` (a `gemma2:2b` tidy-up pass — formatting only, never rewording),
`pages`, `dpi` (default `200`), `gray`, `out_dir`, `work_dir`. The menu asks for input /
formats / cleanup / pages / out-dir.

```
ingest     -> work/pages.json + work/pages/*.png   (rasterize image/PDF)
transcribe -> work/transcribed.json                (Ollama VLM + on-disk cache)
assemble   -> work/transcript.json                 (canonical; optional cleanup tidy)
render     -> output/<name>.{md,txt,docx,pdf}
```

`md`/`txt`/`pdf` are produced with the standard library + PyMuPDF; `docx` uses `python-docx`.

**Limitations:** a 3B VLM exceeds a 2 GB GPU and offloads to CPU (slow per page);
math/equations and diagrams are best-effort only (sketches are not vectorized); Norwegian
handwriting support is thinner than English (proofread names/numbers); layout is
reconstructed as a clean linear document, not a pixel-faithful copy.

---

## convert

Extract a document's existing text into LLM-friendly Markdown or plain text — **offline, with
no model**. This is the cheap extraction path: it reads what the file already contains and
writes it out, so the result can be fed to an LLM (summaries, Q&A, RAG) or read directly.

Four single-purpose scripts, each a pure `name(in_path) -> str` function:

| Script | Conversion | Tool |
|--------|------------|------|
| `convert/pdf_to_md.py`  | PDF → Markdown    | `pymupdf4llm` (keeps headings/tables/reading order) |
| `convert/pdf_to_txt.py` | PDF → plain text  | PyMuPDF `get_text` |
| `convert/docx_to_md.py` | Word `.docx` → Markdown | `markitdown` |
| `convert/pptx_to_md.py` | PowerPoint `.pptx` → Markdown | `markitdown` |

Run a script with `-m` (module form, so the `convert` package resolves; writes a sibling file
by default; `-o` overrides; multiple inputs are allowed):

```powershell
uv run python -m tools.convert.pdf_to_md report.pdf            # -> report.md
uv run python -m tools.convert.pdf_to_txt a.pdf b.pdf          # -> a.txt, b.txt
uv run python -m tools.convert.docx_to_md notes.docx -o out.md
```

Or call the function (returns the converted text as a string):

```python
from tools.convert.pptx_to_md import pptx_to_md
md = pptx_to_md("deck.pptx")
```

From the menu, `convert` reads from `input/` and writes to `output/` (the `-m` scripts above
default to a sibling of the input file).

**Note on offline ≠ no-LLM-limit:** convert never calls an LLM, so any size document converts
fine. But it does **not** remove a downstream LLM's context window — feeding a very long result
into a single prompt still hits that limit. Chunk the output (per section/page) for long docs.

**Limitations:** born-digital input only — scanned/image-only PDFs have no text layer, so use
**transcribe** (OCR/VLM) for those. No page-range selection. The Office path pulls
`markitdown` (which bundles a local ML file-type classifier, `onnxruntime` — offline, but a
heavy dependency).

---

## Shared model mapper

`core/models.json` is the single source of truth for which Ollama model each tool/role
uses; `core/modelmap.py` reads it. Both tools take their default model from here (an
explicit `model=` argument to `pipeline()` overrides it).

```json
{
  "translate":  { "translate": "gemma2:2b" },
  "transcribe": { "transcribe": "qwen2.5vl:3b", "cleanup": "gemma2:2b" }
}
```

Override without editing the file via an env var, e.g.
`OLLAMA_MODEL_TRANSCRIBE_TRANSCRIBE=moondream`.

### Custom LLM endpoint (OpenAI-compatible)

By default the tools call a local Ollama server (`core/ollama.py`). For pointing at a
server that speaks the OpenAI API (`/v1/chat/completions`) — LM Studio, llama.cpp's
server, vLLM, Jan, or Ollama's own `/v1` endpoint — there is an optional, drop-in client
at [`core/openai_compat.py`](core/openai_compat.py). It mirrors `core.ollama.chat`
(including a vision helper) and is configured via env vars:

```powershell
$env:OPENAI_BASE_URL = "http://localhost:1234/v1"   # default: http://localhost:11434/v1
$env:OPENAI_API_KEY  = "sk-..."                      # optional; omit for local servers
```

It is not wired into the pipelines yet — to use it, inject it as the tool's callable
(e.g. pass a `translator` / `transcriber` to `pipeline()` that calls `openai_compat.chat`).

## Tests

```powershell
uv run pytest -q
```

The suite runs without Ollama (the model calls are mocked).

See `docs/specs/` and `docs/plans/` for per-feature design specs and implementation plans
(the original `translate` work and the `convert` tools).
