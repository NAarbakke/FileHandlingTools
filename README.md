# pdftranslate

Translate a born-digital PDF while keeping its original layout and figures.

It reads each text block with its position, removes only the original text
(figures, charts, photos, and vector graphics are left untouched), translates
with a local **Ollama** model, and inserts the translation back into the same
boxes (shrinking the font to fit).

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Install Ollama (https://ollama.com) and pull a multilingual model:

```powershell
ollama pull gemma2:9b      # default; gemma2:2b is lighter, aya-expanse:8b is translation-focused
```

## Usage

```powershell
python -m pdftranslate input.pdf --to no --model gemma2:9b
```

Output: `output/<name>.no.pdf` plus before/after QA images in `output/qa/`.

Useful flags:

| Flag | Meaning |
|------|---------|
| `--from en` | source language (default `en`) |
| `--to no` | target language (default `no`) |
| `--model gemma2:9b` | Ollama model |
| `--pages 1-5` | process only these pages (1-based); others copied unchanged |
| `--skip-translate` | reuse the cached translation for a fast rebuild |
| `--no-qa` | skip the QA image render |
| `--out-dir` / `--work-dir` | output / intermediate directories |

## How it works

```
extract  -> work/blocks.json
translate-> work/blocks.<lang>.json   (Ollama + on-disk cache)
rebuild  -> output/<name>.<lang>.pdf   (redact text, keep figures, insert translation)
render_qa-> output/qa/*.png            (original vs translated)
```

Each stage reads/writes a file, so any stage can be inspected or re-run alone.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The suite runs without Ollama (translation is mocked).

## Known limitations (v1)

- Born-digital PDFs only — no OCR for scanned/image-only pages.
- Typeface/bold/italic not reproduced; text is re-inserted in one embedded font
  (DejaVu Sans) at the original size and color.
- Inline equations are skipped (left as the original).
- Assumes a white page background (redaction fills removed text with white).

See `docs/specs/` and `docs/plans/` for the full design and implementation plan.
