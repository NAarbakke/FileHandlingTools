# FileHandlingTools

Local, open-source document tools, run from **one terminal menu** and sharing a single
Ollama model configuration. Everything runs on your machine — no cloud, no API keys.

| Tool | What it does |
|------|--------------|
| **translate**  | translate a born-digital PDF, keeping its original layout and figures |
| **transcribe** | transcribe handwritten notes (photo, scan, or PDF) into md / txt / docx / pdf |

Which model each tool uses is defined once in [`models.json`](models.json) — see
[Shared model mapper](#shared-model-mapper).

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

Pick a tool by number; it prompts for the input file and a few options, runs the
pipeline, and writes to `output/`. Choose `0` to quit.

```
FileHandlingTools
=================
 1) translate    translate a PDF, keep layout
 2) transcribe   handwritten notes -> md/txt/docx/pdf
 0) quit

Select a tool [1]: 2
  input image/PDF: notes.jpg
  formats [md]: md,docx,pdf
  cleanup pass? [y/N]: n
  ... running ...
  wrote: output/notes.md, output/notes.docx, output/notes.pdf
```

### Scripting (optional)

Each tool is also a plain importable function, so you can drive it from Python:

```python
import translate, transcribe

translate.pipeline("paper.pdf", tgt="no")                       # -> output/paper.no.pdf
transcribe.pipeline("notes.jpg", formats=["md", "docx", "pdf"], cleanup=True)
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

## Shared model mapper

`models.json` at the repo root is the single source of truth for which Ollama model each
tool/role uses; `modelmap.py` reads it. Both tools take their default model from here (an
explicit `model=` argument to `pipeline()` overrides it).

```json
{
  "translate":  { "translate": "gemma2:2b" },
  "transcribe": { "transcribe": "qwen2.5vl:3b", "cleanup": "gemma2:2b" }
}
```

Override without editing the file via an env var, e.g.
`OLLAMA_MODEL_TRANSCRIBE_TRANSCRIBE=moondream`.

## Tests

```powershell
uv run pytest -q
```

The suite runs without Ollama (the model calls are mocked).

See `docs/specs/` and `docs/plans/` for the original `translate` design and implementation plan.
