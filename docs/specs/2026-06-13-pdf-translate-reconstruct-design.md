# PDF Translate-and-Reconstruct — Design Spec (v1)

- **Date:** 2026-06-13
- **Status:** Approved for planning
- **Owner:** Nikolai
- **Home:** `C:\Users\admin1\Documents\Projects\FileHandlingTool\`

## 1. Goal

Take a born-digital PDF report, translate its text, and produce a new PDF that
looks like the original — same layout, same figures, charts, photos, and
vector graphics — but with the body text replaced by its translation.

v1 target language pair: **English → Norwegian (Bokmål)**. The pair is
configurable; v1 is built and tuned against one concrete pair.

Test document: `aerospace-10-00563.pdf` (MDPI *Aerospace* paper — two-column,
figures, equations). A deliberately hard case, used to set honest expectations.

## 2. Non-goals (v1)

- Scanned / image-only PDFs with no text layer (would need OCR).
- Perfect mathematics / equation translation.
- Right-to-left or complex-shaping scripts (Arabic, etc.).
- Re-flowing text across page boundaries or rebuilding the document model.
- A GUI. v1 is a command-line tool.

## 3. Approach decision: in-place overlay (not reflow)

Two architectures were considered:

- **Reflow** (markitdown / pdftotext → translate → pandoc re-render): easy to
  write but produces a *new* document. Original layout, columns, and figure
  placement are lost. **Rejected** — it fails the core requirement.
- **In-place overlay (chosen):** open the real PDF, read each text block *with
  its bounding box*, remove **only** the original text via redaction, then
  insert the translated text into the same box. Images, charts, vector art, and
  backgrounds are never touched, so they are preserved exactly and the layout is
  unchanged.

**Consequence:** PyMuPDF alone is the engine. markitdown, pdftotext, and pandoc
are not used — they belong to the rejected reflow approach and would add
complexity while reducing fidelity.

## 4. Architecture — four stages, one shared data file

```
input.pdf
  → [extract]    PyMuPDF reads text blocks            → work/blocks.json
  → [translate]  each block → Ollama (EN→NO) + cache   → work/blocks.no.json
  → [rebuild]    reopen ORIGINAL pdf, redact text,
                 insert translated text (shrink-to-fit) → output/<name>.no.pdf
  → [render_qa]  render original vs translated pages    → output/qa/*.png
```

Each stage reads/writes a file on disk, so any stage can be inspected or re-run
independently. `blocks.json` is the contract between stages.

### 4.1 Data contract — `blocks.json`

```json
{
  "source_pdf": "aerospace-10-00563.pdf",
  "source_lang": "en",
  "target_lang": "no",
  "page_count": 18,
  "pages": [
    {
      "page": 0,
      "width": 595.32,
      "height": 841.92,
      "blocks": [
        {
          "id": "p0_b2",
          "bbox": [72.0, 110.4, 523.2, 138.7],
          "text": "Abstract: This paper presents ...",
          "size": 9.96,
          "color": 2105376,
          "skip": false,
          "skip_reason": null
        }
      ]
    }
  ]
}
```

- `bbox`: `[x0, y0, x1, y1]` in PDF points, the block's bounding box.
- `size`: dominant span font size in the block (used when re-inserting).
- `color`: sRGB integer of the first span (converted to RGB on rebuild).
- `skip` / `skip_reason`: see 5.1. Skipped blocks are neither translated nor
  redacted — left exactly as the original.

`blocks.no.json` is `blocks.json` with each non-skipped block gaining
`"text_translated": "..."`.

## 5. Component specs

### 5.1 `extract.py`
- Input: a PDF path. Output: `work/blocks.json`.
- Uses `page.get_text("dict")`; for each **text** block, joins its lines/spans
  into one string, takes the block `bbox`, the most common span `size`, and the
  first span `color`.
- **Skip heuristic** (mark `skip=true`, leave untouched on rebuild) when a block
  is non-translatable: empty/whitespace; or a high ratio of digits/symbols to
  letters (math, equation fragments, axis labels, bare page numbers). The exact
  thresholds are an implementation detail; err toward *not* skipping real prose.

### 5.2 `translate.py`
- Input: `work/blocks.json`. Output: `work/blocks.no.json`.
- For each non-skipped block, call the local **Ollama** chat API
  (`POST http://localhost:11434/api/chat`, `stream:false`,
  `options.temperature:0.2`).
- **System prompt:** instruct the model to translate from source to target
  language, output **only** the translation (no notes, no quotes), preserve
  numbers/units/inline formatting, and return proper nouns/acronyms unchanged.
- **Cache:** key = `sha256(model + src + tgt + text)`, stored under
  `work/cache/`. Re-runs reuse cached translations, so iterating on rebuild is
  fast and re-translation is avoided.
- v1 is sequential (simple) + cache. A small thread pool is a later optimization.
- Must be testable without Ollama running, via an injectable "echo/mock"
  translator.

### 5.3 `rebuild.py`
- Input: original PDF + `work/blocks.no.json`. Output: `output/<name>.no.pdf`.
- Embeds a vendored Unicode font (see 6) so any character the model emits
  renders correctly.
- **Per page, strict ordering:**
  1. For every non-skipped block, add a text-only redaction annotation over its
     `bbox`.
  2. `apply_redactions(images=PDF_REDACT_IMAGE_NONE,
     graphics=PDF_REDACT_LINE_ART_NONE)` **once** — removes the original text
     glyphs while leaving images and vector graphics intact.
  3. *Then* insert translated text. (Redactions must be applied before
     insertion, or they would wipe freshly inserted text.)
- **Shrink-to-fit:** insert with `insert_textbox(rect, text, fontsize=size, …)`
  starting at the original size; if the return value is negative (overflow),
  reduce font size by 0.5pt and retry down to a 4pt floor. Guarantees the
  translation fits its box even when Norwegian runs longer.
- `color` int → RGB floats: `r=(c>>16&255)/255, g=(c>>8&255)/255, b=(c&255)/255`.

### 5.4 `render_qa.py`
- Renders the first N pages (default 3) of the original and the translated PDF
  to PNGs at 150 dpi into `output/qa/` for a quick visual check that figures
  survived and text is translated. Side-by-side composition is optional/later.

### 5.5 `cli.py`
- `python -m pdftranslate INPUT.pdf [--from en] [--to no] [--model gemma2:9b]
  [--pages 1-5] [--skip-translate] [--no-qa] [--out-dir output]`
- Runs extract → translate → rebuild → render_qa in order, printing progress.
- `--skip-translate` reuses `blocks.no.json` / cache for fast rebuild iteration.
- `--pages 1-5` restricts processing to those pages (1-based); all other pages
  are copied into the output unchanged (original text retained). Useful for fast
  iteration on a single page. Default: all pages.

## 6. Stack, dependencies, layout

- **Python 3.13** (installed at `C:\Users\admin1\AppData\Local\Programs\Python\Python313`).
- **Dependencies — two only:** `pymupdf` (engine) + `requests` (Ollama HTTP).
- **Ollama** (local) — installed by the user; see 7. Model is a CLI flag.
  Recommended for EN→NO: `gemma2:9b` (default), `aya-expanse:8b`
  (translation-focused alternative), or `gemma2:2b` (lightweight).
- **Font:** vendor `assets/DejaVuSans.ttf` (open license, full Latin + `æ ø å`),
  copied during scaffolding from the existing matplotlib install
  (`…/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf`) so nothing is downloaded.
  Embedded on rebuild. (Norwegian alone fits base-14/WinAnsi, but a Unicode font
  is vendored for robustness and future languages.)

```
FileHandlingTool/
├─ pdftranslate/
│  ├─ __init__.py
│  ├─ __main__.py        # enables `python -m pdftranslate`
│  ├─ extract.py
│  ├─ translate.py
│  ├─ rebuild.py
│  ├─ render_qa.py
│  ├─ cli.py
│  └─ assets/DejaVuSans.ttf
├─ tests/               # fixtures: tiny blocks.json / blocks.no.json
├─ work/                # blocks.json, blocks.no.json, cache/  (gitignored)
├─ output/              # <name>.no.pdf, qa/*.png            (gitignored)
├─ docs/specs/2026-06-13-pdf-translate-reconstruct-design.md
├─ aerospace-10-00563.pdf   # test file
├─ requirements.txt
└─ README.md
```

## 7. Setup prerequisites (one-time, before first run)

1. Install Ollama (`winget install Ollama.Ollama`, or download from ollama.com).
2. `ollama pull gemma2:9b` (or the chosen model).
3. Ensure the Ollama server is running (tray app / `ollama serve`); API at
   `http://localhost:11434`.
4. Create a venv in `FileHandlingTool\` and `pip install -r requirements.txt`.

## 8. Known limitations / honest expectations (v1)

- **Typeface/styling not preserved:** each block is re-inserted as a single run
  in the embedded font (DejaVuSans) at one size and color. Original fonts,
  bold/italic, and per-span styling are not reproduced — only layout position,
  size, and color are. (This is why `blocks.json` carries `size`+`color` but not
  `font`.) Reproducing original styling is a future extension.
- Norwegian runs ~10–15% longer than English; shrink-to-fit handles overflow,
  but a rare long phrase in a tight box may shrink noticeably small.
- Two-column reading order is usually correct but not guaranteed.
- Inline equations may be mangled; v1 skips blocks that look like math and
  leaves them as the original.
- Headers/footers/captions are translated like any other prose unless caught by
  the skip heuristic.

## 9. Acceptance criteria (how we know v1 works)

1. `python -m pdftranslate aerospace-10-00563.pdf --to no` runs end-to-end with
   no errors (assuming Ollama up + model pulled).
2. `output/aerospace-10-00563.no.pdf` opens, has the **same page count**, and its
   figures/charts are **visibly present and unchanged**.
3. Body text in the output is Norwegian.
4. QA PNGs in `output/qa/` show original vs translated with figures intact.
5. A second run with `--skip-translate` (or warm cache) does no re-translation
   and is fast.
6. Unit tests pass: extract produces contract-valid `blocks.json` on the sample;
   translate works against a mock translator; rebuild produces a valid PDF from a
   fixture `blocks.no.json`.

## 10. Future extensions (explicitly out of v1)

- OCR path (Tesseract / OCRmyPDF) for scanned PDFs.
- Math-aware handling.
- Additional / non-Latin languages and RTL.
- Parallel translation; batching multiple blocks per request.
- Side-by-side QA composition; full-document visual diff.

## 11. Build approach (subagents)

- **Phase 0 (orchestrator):** scaffold repo, venv, `requirements.txt`, vendor the
  font, write the `blocks.json` contract + test fixtures and shared helpers
  (paths, color conversion). The shared contract must exist before subagents.
- **Parallel subagents along clean seams** (each gets the contract + a fixture so
  it can be built and tested in isolation, TDD):
  - **A — extract:** `extract.py` + skip heuristic. Verified on the sample PDF.
  - **B — translate:** `translate.py` + Ollama client + cache. Verified against a
    mock translator (no Ollama needed in tests).
  - **C — rebuild + QA:** `rebuild.py` + `render_qa.py`. Verified from a
    hand-made `blocks.no.json` fixture.
- **Integration (orchestrator):** wire `cli.py`, then run the full pipeline on
  `aerospace-10-00563.pdf` and check the acceptance criteria.

The exact task split is finalized in the implementation plan (writing-plans).
