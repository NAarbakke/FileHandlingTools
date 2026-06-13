# PDF Translate-and-Reconstruct Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A command-line tool that translates a born-digital PDF and rebuilds it with the original layout and figures intact but the text replaced by its translation.

**Architecture:** In-place overlay with PyMuPDF — read each text block with its bounding box, redact only the original text (images/vector graphics untouched), insert translated text into the same box with shrink-to-fit. Four file-based stages (extract → translate → rebuild → render_qa) tied together by a CLI. Translation is done by a local Ollama model; the translate stage takes an injectable translator so it is testable without Ollama.

**Tech Stack:** Python 3.13, PyMuPDF (`fitz`), stdlib `urllib.request` (Ollama HTTP — no `requests` dependency), Ollama (local LLM runtime), pytest.

Spec: `docs/specs/2026-06-13-pdf-translate-reconstruct-design.md`.

---

## Prerequisites & conventions

- **Working directory for all commands:** `C:\Users\admin1\Documents\Projects\FileHandlingTool` (already a git repo).
- **Virtual environment:** activate the project venv (`.venv`) before running `python`/`pytest`. PowerShell: `.\.venv\Scripts\Activate.ps1`.
- **Every commit message must end with this trailer** (omitted from the commands below for brevity — append it to each):
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```
- **Deviation from spec (intentional simplification):** the spec listed `requests`; this plan uses stdlib `urllib.request` instead, so PyMuPDF is the *only* runtime dependency. This is strictly fewer dependencies.
- **Assumption made explicit:** redaction paints white `(1,1,1)` over removed-text boxes, which assumes a white page background (true for the target paper). Colored-background pages are out of scope for v1.

## Subagent mapping (if using subagent-driven-development)

- Orchestrator: Task 1 (scaffold), Task 7 (CLI), Task 8 (Ollama setup), Task 9 (integration), Task 10 (README).
- Agent A: Task 2 (common) + Task 3 (extract).
- Agent B: Task 4 (translate).
- Agent C: Task 5 (rebuild) + Task 6 (render_qa).

Tasks 3, 4, 5, 6 are mutually independent once Tasks 1–2 land, so they may be parallelized; sequential-with-review is safer and recommended.

---

## Task 1: Project scaffold & environment

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`
- Create: `pdftranslate/__init__.py`, `pdftranslate/__main__.py`
- Create: `pdftranslate/assets/DejaVuSans.ttf` (copied, not authored)
- Create: `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Create the package and test directories with placeholder files**

`pdftranslate/__init__.py`:
```python
"""PDF translate-and-reconstruct: keep layout and figures, replace text."""
__version__ = "0.1.0"
```

`pdftranslate/__main__.py`:
```python
from .cli import main

main()
```

`tests/__init__.py`: empty file.

- [ ] **Step 2: Write `requirements.txt` and `requirements-dev.txt`**

`requirements.txt`:
```
pymupdf>=1.24
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8
```

- [ ] **Step 3: Create the venv and install dependencies**

Run (PowerShell):
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```
Expected: installs PyMuPDF and pytest without error.

- [ ] **Step 4: Verify PyMuPDF imports**

Run: `python -c "import fitz; print(fitz.__doc__.splitlines()[0])"`
Expected: prints a PyMuPDF version banner, no ImportError.

- [ ] **Step 5: Vendor the Unicode font (copy from the existing matplotlib install)**

Run (PowerShell — finds DejaVuSans.ttf already on disk and copies it into assets):
```
New-Item -ItemType Directory -Force -Path pdftranslate\assets | Out-Null
$src = Get-ChildItem -Path C:\Users\admin1\Documents\Projects -Recurse -Filter DejaVuSans.ttf -ErrorAction SilentlyContinue | Select-Object -First 1
Copy-Item $src.FullName pdftranslate\assets\DejaVuSans.ttf
Test-Path pdftranslate\assets\DejaVuSans.ttf
```
Expected: prints `True`. (If no font is found, download DejaVuSans.ttf from the dejavu-fonts project and place it at that path.)

- [ ] **Step 6: Write `tests/conftest.py` with a tiny in-memory PDF fixture**

`tests/conftest.py`:
```python
import fitz
import pytest


@pytest.fixture
def tiny_pdf(tmp_path):
    """A 1-page PDF with two text lines and one vector 'figure' (a filled rect)."""
    path = tmp_path / "tiny.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((20, 40), "Hello world", fontsize=12)
    page.insert_text((20, 80), "Second line here", fontsize=12)
    page.draw_rect(fitz.Rect(20, 110, 120, 170), color=(0, 0, 1), fill=(0.8, 0.8, 1.0))
    doc.save(str(path))
    doc.close()
    return str(path)
```

- [ ] **Step 7: Confirm the test harness runs (zero tests is fine)**

Run: `pytest -q`
Expected: `no tests ran` (or collects 0) with exit code 0 — confirms pytest + conftest import cleanly.

- [ ] **Step 8: Commit**

```
git add requirements.txt requirements-dev.txt pdftranslate tests
git commit -m "chore: scaffold pdftranslate package, venv deps, font, test harness"
```
(Note: `.venv/` is already gitignored; the vendored font IS committed.)

---

## Task 2: `common.py` — color conversion + skip heuristic

**Files:**
- Create: `pdftranslate/common.py`
- Test: `tests/test_common.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_common.py`:
```python
from pdftranslate.common import color_int_to_rgb, looks_untranslatable


def test_color_white():
    assert color_int_to_rgb(0xFFFFFF) == (1.0, 1.0, 1.0)


def test_color_black():
    assert color_int_to_rgb(0) == (0.0, 0.0, 0.0)


def test_color_red():
    assert color_int_to_rgb(0xFF0000) == (1.0, 0.0, 0.0)


def test_untranslatable_blank():
    assert looks_untranslatable("   ") is True


def test_untranslatable_bare_number():
    assert looks_untranslatable("12") is True


def test_untranslatable_equation():
    assert looks_untranslatable("x = a^2 + b^2") is True


def test_translatable_sentence():
    assert looks_untranslatable("This is a normal sentence.") is False


def test_translatable_heading():
    assert looks_untranslatable("3. Methodology and Results") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_common.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pdftranslate.common'`.

- [ ] **Step 3: Implement `common.py`**

`pdftranslate/common.py`:
```python
"""Shared helpers: color conversion and the non-prose skip heuristic."""
from __future__ import annotations

import re

_LETTER_RE = re.compile(r"[A-Za-zÀ-ÿ]")


def color_int_to_rgb(color):
    """Convert a PyMuPDF sRGB integer to an (r, g, b) tuple of 0..1 floats."""
    if color is None:
        return (0.0, 0.0, 0.0)
    r = (color >> 16) & 255
    g = (color >> 8) & 255
    b = color & 255
    return (r / 255.0, g / 255.0, b / 255.0)


def looks_untranslatable(text):
    """True if a block is non-prose (blank, bare number, equation, symbols).

    Such blocks are left exactly as the original: not translated, not redacted.
    Errs toward translating — only short, letter-poor blocks are skipped.
    """
    stripped = text.strip()
    if not stripped:
        return True
    letters = len(_LETTER_RE.findall(stripped))
    if letters == 0:
        return True
    letter_ratio = letters / len(stripped)
    if letter_ratio < 0.4 and len(stripped) < 60:
        return True
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_common.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```
git add pdftranslate/common.py tests/test_common.py
git commit -m "feat: add color conversion and non-prose skip heuristic"
```

---

## Task 3: `extract.py` — text blocks with positions → blocks.json

**Files:**
- Create: `pdftranslate/extract.py`
- Test: `tests/test_extract.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_extract.py`:
```python
import json

from pdftranslate.extract import extract_document, run

REQUIRED_BLOCK_KEYS = {"id", "bbox", "text", "size", "color", "skip", "skip_reason"}


def test_extract_structure(tiny_pdf):
    doc = extract_document(tiny_pdf, source_lang="en", target_lang="no")
    assert doc["source_lang"] == "en"
    assert doc["target_lang"] == "no"
    assert doc["page_count"] == 1
    assert len(doc["pages"]) == 1
    page = doc["pages"][0]
    assert page["page"] == 0
    assert page["width"] == 300
    assert page["height"] == 200
    assert page["blocks"], "expected at least one text block"
    for b in page["blocks"]:
        assert REQUIRED_BLOCK_KEYS.issubset(b)
        assert len(b["bbox"]) == 4


def test_extract_finds_text(tiny_pdf):
    doc = extract_document(tiny_pdf, source_lang="en", target_lang="no")
    all_text = " ".join(b["text"] for b in doc["pages"][0]["blocks"])
    assert "Hello world" in all_text
    assert "Second line here" in all_text


def test_extract_pages_filter(tiny_pdf):
    doc = extract_document(tiny_pdf, source_lang="en", target_lang="no", pages={5})
    # page 5 doesn't exist -> no pages processed, but total count still reported
    assert doc["page_count"] == 1
    assert doc["pages"] == []


def test_run_writes_json(tiny_pdf, tmp_path):
    out = tmp_path / "blocks.json"
    run(tiny_pdf, str(out), source_lang="en", target_lang="no")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["source_pdf"].endswith("tiny.pdf")
    assert data["pages"][0]["blocks"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_extract.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pdftranslate.extract'`.

- [ ] **Step 3: Implement `extract.py`**

`pdftranslate/extract.py`:
```python
"""Stage 1: extract text blocks (with positions) from a PDF into blocks.json."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

from .common import looks_untranslatable


def _extract_page(page, pno):
    data = page.get_text("dict")
    blocks = []
    bidx = 0
    for block in data.get("blocks", []):
        if block.get("type", 0) != 0:
            continue  # image block — left untouched in the PDF
        lines_text = []
        sizes = []
        first_color = 0
        have_color = False
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            lines_text.append("".join(s.get("text", "") for s in spans))
            for s in spans:
                sizes.append(round(s.get("size", 0.0), 2))
                if not have_color:
                    first_color = s.get("color", 0)
                    have_color = True
        text = " ".join(t for t in lines_text if t)
        if not text.strip():
            continue
        size = Counter(sizes).most_common(1)[0][0] if sizes else 10.0
        skip = looks_untranslatable(text)
        blocks.append({
            "id": f"p{pno}_b{bidx}",
            "bbox": [round(c, 2) for c in block["bbox"]],
            "text": text,
            "size": size,
            "color": first_color,
            "skip": skip,
            "skip_reason": "non-prose" if skip else None,
        })
        bidx += 1
    return {
        "page": pno,
        "width": round(page.rect.width, 2),
        "height": round(page.rect.height, 2),
        "blocks": blocks,
    }


def extract_document(pdf_path, *, source_lang="en", target_lang="no", pages=None):
    """Return the blocks.json contract dict. `pages` = set of 0-based indices or None."""
    doc = fitz.open(pdf_path)
    try:
        page_count = doc.page_count
        out_pages = []
        for pno in range(page_count):
            if pages is not None and pno not in pages:
                continue
            out_pages.append(_extract_page(doc.load_page(pno), pno))
    finally:
        doc.close()
    return {
        "source_pdf": Path(pdf_path).name,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "page_count": page_count,
        "pages": out_pages,
    }


def run(pdf_path, out_path, *, source_lang="en", target_lang="no", pages=None):
    doc = extract_document(pdf_path, source_lang=source_lang, target_lang=target_lang, pages=pages)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_extract.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```
git add pdftranslate/extract.py tests/test_extract.py
git commit -m "feat: extract text blocks with positions into blocks.json"
```

---

## Task 4: `translate.py` — Ollama client, cache, orchestration

**Files:**
- Create: `pdftranslate/translate.py`
- Test: `tests/test_translate.py`

- [ ] **Step 1: Write the failing tests** (all use a mock translator — no Ollama needed)

`tests/test_translate.py`:
```python
from pdftranslate import translate


def make_doc():
    return {
        "source_pdf": "x.pdf",
        "source_lang": "en",
        "target_lang": "no",
        "page_count": 1,
        "pages": [{
            "page": 0, "width": 300, "height": 200, "blocks": [
                {"id": "p0_b0", "bbox": [0, 0, 10, 10], "text": "Hello",
                 "size": 12, "color": 0, "skip": False, "skip_reason": None},
                {"id": "p0_b1", "bbox": [0, 0, 10, 10], "text": "12",
                 "size": 12, "color": 0, "skip": True, "skip_reason": "non-prose"},
            ],
        }],
    }


def test_translates_non_skip_only():
    doc = make_doc()
    translate.translate_document(doc, translator=lambda t: f"[NO]{t}")
    b0, b1 = doc["pages"][0]["blocks"]
    assert b0["text_translated"] == "[NO]Hello"
    assert "text_translated" not in b1  # skipped blocks are left alone


def test_cache_avoids_second_call(tmp_path):
    calls = {"n": 0}

    def tr(t):
        calls["n"] += 1
        return f"[NO]{t}"

    cache = str(tmp_path / "cache")
    translate.translate_document(make_doc(), translator=tr, cache_dir=cache)
    translate.translate_document(make_doc(), translator=tr, cache_dir=cache)
    assert calls["n"] == 1  # second run is served entirely from cache


def test_cache_key_is_stable():
    k1 = translate.cache_key("m", "en", "no", "Hello")
    k2 = translate.cache_key("m", "en", "no", "Hello")
    k3 = translate.cache_key("m", "en", "no", "Goodbye")
    assert k1 == k2 != k3


def test_run_writes_translated_json(tmp_path):
    import json
    blocks = tmp_path / "blocks.json"
    blocks.write_text(json.dumps(make_doc()), encoding="utf-8")
    out = tmp_path / "blocks.no.json"
    translate.run(str(blocks), str(out), translator=lambda t: f"[NO]{t}")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["pages"][0]["blocks"][0]["text_translated"] == "[NO]Hello"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_translate.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pdftranslate.translate'`.

- [ ] **Step 3: Implement `translate.py`**

`pdftranslate/translate.py`:
```python
"""Stage 2: translate each non-skip block via Ollama, with an on-disk cache."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"

LANG_NAMES = {"en": "English", "no": "Norwegian (Bokmål)"}

SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text from {src} to {tgt}. "
    "Output ONLY the translation, with no preamble, notes, or quotation marks. "
    "Preserve numbers, units, math, and inline formatting. "
    "Leave proper nouns, acronyms, and citation markers unchanged."
)


class OllamaTranslator:
    """Callable translator backed by a local Ollama chat model."""

    def __init__(self, model="gemma2:9b", url=OLLAMA_URL, src="en", tgt="no", temperature=0.2, timeout=300):
        self.model = model
        self.url = url
        self.timeout = timeout
        self.temperature = temperature
        self.system = SYSTEM_PROMPT.format(
            src=LANG_NAMES.get(src, src), tgt=LANG_NAMES.get(tgt, tgt)
        )

    def __call__(self, text):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system},
                {"role": "user", "content": text},
            ],
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["message"]["content"].strip()


def cache_key(model, src, tgt, text):
    raw = f"{model}\x00{src}\x00{tgt}\x00{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def translate_document(doc, translator, cache_dir=None, progress=None):
    """Add `text_translated` to every non-skip block. Mutates and returns `doc`."""
    src, tgt = doc["source_lang"], doc["target_lang"]
    model = getattr(translator, "model", "mock")
    cache = Path(cache_dir) if cache_dir else None
    if cache:
        cache.mkdir(parents=True, exist_ok=True)

    pending = [b for p in doc["pages"] for b in p["blocks"] if not b.get("skip")]
    total = len(pending)
    for done, blk in enumerate(pending, start=1):
        text = blk["text"]
        cfile = cache / f"{cache_key(model, src, tgt, text)}.txt" if cache else None
        if cfile is not None and cfile.exists():
            translated = cfile.read_text(encoding="utf-8")
        else:
            translated = translator(text)
            if cfile is not None:
                cfile.write_text(translated, encoding="utf-8")
        blk["text_translated"] = translated
        if progress:
            progress(done, total)
    return doc


def run(blocks_path, out_path, *, model="gemma2:9b", cache_dir=None, translator=None, progress=None):
    doc = json.loads(Path(blocks_path).read_text(encoding="utf-8"))
    if translator is None:
        translator = OllamaTranslator(model=model, src=doc["source_lang"], tgt=doc["target_lang"])
    translate_document(doc, translator, cache_dir=cache_dir, progress=progress)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_translate.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```
git add pdftranslate/translate.py tests/test_translate.py
git commit -m "feat: add Ollama translator with on-disk cache and orchestration"
```

---

## Task 5: `rebuild.py` — redact original text, insert translation, keep figures

**Files:**
- Create: `pdftranslate/rebuild.py`
- Test: `tests/test_rebuild.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_rebuild.py`:
```python
import fitz

from pdftranslate.extract import extract_document
from pdftranslate import rebuild


def test_rebuild_redacts_and_inserts(tiny_pdf, tmp_path):
    doc = extract_document(tiny_pdf, source_lang="en", target_lang="no")
    # translate just the first text block by hand
    first = doc["pages"][0]["blocks"][0]
    original = first["text"]
    first["text_translated"] = "Hei verden"

    out = tmp_path / "out.pdf"
    rebuild.rebuild_pdf(tiny_pdf, doc, str(out))

    assert out.exists()
    res = fitz.open(str(out))
    try:
        assert res.page_count == 1
        text = res.load_page(0).get_text()
        assert "Hei verden" in text          # translation inserted
        assert original not in text          # original text removed
    finally:
        res.close()


def test_rebuild_keeps_page_count(tiny_pdf, tmp_path):
    doc = extract_document(tiny_pdf, source_lang="en", target_lang="no")
    for b in doc["pages"][0]["blocks"]:
        b["text_translated"] = "x"
    out = tmp_path / "out.pdf"
    rebuild.rebuild_pdf(tiny_pdf, doc, str(out))
    src = fitz.open(tiny_pdf)
    res = fitz.open(str(out))
    try:
        assert res.page_count == src.page_count
    finally:
        src.close()
        res.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rebuild.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pdftranslate.rebuild'`.

- [ ] **Step 3: Implement `rebuild.py`**

`pdftranslate/rebuild.py`:
```python
"""Stage 3: rebuild the PDF — redact original text, insert translated text.

Figures, photos, and vector graphics are preserved by removing ONLY text during
redaction (images and line-art are explicitly kept).
"""
from __future__ import annotations

from pathlib import Path

import fitz

from .common import color_int_to_rgb

FONT_FILE = Path(__file__).parent / "assets" / "DejaVuSans.ttf"
FONT_NAME = "djv"
MIN_FONT_SIZE = 4.0


def _insert_fit(page, rect, text, size, color):
    """Insert text into rect, shrinking the font until it fits (down to a floor)."""
    fs = float(size)
    while fs >= MIN_FONT_SIZE:
        rc = page.insert_textbox(rect, text, fontname=FONT_NAME, fontsize=fs, color=color, align=0)
        if rc >= 0:
            return
        fs -= 0.5
    page.insert_textbox(rect, text, fontname=FONT_NAME, fontsize=MIN_FONT_SIZE, color=color, align=0)


def rebuild_pdf(src_pdf, doc, out_path):
    """Write a translated copy of `src_pdf` using translations in `doc` (blocks.no)."""
    pdf = fitz.open(src_pdf)
    try:
        for page_data in doc["pages"]:
            page = pdf.load_page(page_data["page"])
            page.insert_font(fontname=FONT_NAME, fontfile=str(FONT_FILE))
            targets = [b for b in page_data["blocks"]
                       if not b.get("skip") and "text_translated" in b]
            if not targets:
                continue
            # 1) remove original text (keep images + vector graphics)
            for blk in targets:
                page.add_redact_annot(fitz.Rect(blk["bbox"]), fill=(1, 1, 1), cross_out=False)
            page.apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_NONE,
                graphics=fitz.PDF_REDACT_LINE_ART_NONE,
            )
            # 2) insert translated text into the same boxes (after redactions)
            for blk in targets:
                _insert_fit(
                    page,
                    fitz.Rect(blk["bbox"]),
                    blk["text_translated"],
                    blk["size"],
                    color_int_to_rgb(blk.get("color", 0)),
                )
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        pdf.save(str(out), garbage=4, deflate=True)
    finally:
        pdf.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rebuild.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```
git add pdftranslate/rebuild.py tests/test_rebuild.py
git commit -m "feat: rebuild PDF by redacting text and inserting translation, keeping figures"
```

---

## Task 6: `render_qa.py` — render pages to PNGs for visual check

**Files:**
- Create: `pdftranslate/render_qa.py`
- Test: `tests/test_render_qa.py`

- [ ] **Step 1: Write the failing test**

`tests/test_render_qa.py`:
```python
from pdftranslate import render_qa


def test_render_pages_writes_pngs(tiny_pdf, tmp_path):
    out = tmp_path / "qa"
    paths = render_qa.render_pages(tiny_pdf, str(out), "original", pages=1, dpi=72)
    assert len(paths) == 1
    assert paths[0].exists()
    assert paths[0].name == "original_p1.png"


def test_run_renders_both(tiny_pdf, tmp_path):
    out = tmp_path / "qa"
    render_qa.run(tiny_pdf, tiny_pdf, str(out), pages=1, dpi=72)
    assert (out / "original_p1.png").exists()
    assert (out / "translated_p1.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_render_qa.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pdftranslate.render_qa'`.

- [ ] **Step 3: Implement `render_qa.py`**

`pdftranslate/render_qa.py`:
```python
"""Stage 4: render the first N pages of original and translated PDFs to PNGs."""
from __future__ import annotations

from pathlib import Path

import fitz


def render_pages(pdf_path, out_dir, prefix, pages=3, dpi=150):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pdf = fitz.open(pdf_path)
    try:
        n = min(pages, pdf.page_count)
        written = []
        for pno in range(n):
            pix = pdf.load_page(pno).get_pixmap(matrix=mat)
            p = out / f"{prefix}_p{pno + 1}.png"
            pix.save(str(p))
            written.append(p)
        return written
    finally:
        pdf.close()


def run(original_pdf, translated_pdf, out_dir, pages=3, dpi=150):
    render_pages(original_pdf, out_dir, "original", pages=pages, dpi=dpi)
    render_pages(translated_pdf, out_dir, "translated", pages=pages, dpi=dpi)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_render_qa.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```
git add pdftranslate/render_qa.py tests/test_render_qa.py
git commit -m "feat: render original vs translated pages to PNGs for QA"
```

---

## Task 7: `cli.py` — wire the four stages together

**Files:**
- Create: `pdftranslate/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:
```python
from pdftranslate import cli


def test_parse_pages():
    assert cli.parse_pages(None) is None
    assert cli.parse_pages("3") == {2}
    assert cli.parse_pages("1-3") == {0, 1, 2}
    assert cli.parse_pages("1-2,5") == {0, 1, 4}


def test_cli_end_to_end_with_mock(tiny_pdf, tmp_path, monkeypatch):
    # Replace the Ollama-backed translator with a mock so no server is needed.
    import pdftranslate.translate as T
    monkeypatch.setattr(T, "OllamaTranslator", lambda **kw: (lambda t: f"NO:{t}"))

    out_dir = tmp_path / "output"
    work_dir = tmp_path / "work"
    cli.main([tiny_pdf, "--to", "no",
              "--out-dir", str(out_dir), "--work-dir", str(work_dir), "--no-qa"])

    import os
    stem = os.path.splitext(os.path.basename(tiny_pdf))[0]
    assert (out_dir / f"{stem}.no.pdf").exists()
    assert (work_dir / "blocks.json").exists()
    assert (work_dir / "blocks.no.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -q`
Expected: FAIL with `AttributeError`/`ModuleNotFoundError` for `pdftranslate.cli`.

- [ ] **Step 3: Implement `cli.py`**

`pdftranslate/cli.py`:
```python
"""Command-line entry point: extract -> translate -> rebuild -> render_qa."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import extract, translate, rebuild, render_qa


def parse_pages(spec):
    """'1-5' / '3' / '1-2,5' (1-based) -> set of 0-based indices. None if empty."""
    if not spec:
        return None
    result = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            result.update(range(int(a) - 1, int(b)))
        else:
            result.add(int(part) - 1)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="pdftranslate",
        description="Translate a PDF while keeping its layout and figures.",
    )
    ap.add_argument("input", help="input PDF path")
    ap.add_argument("--from", dest="src", default="en", help="source language code")
    ap.add_argument("--to", dest="tgt", default="no", help="target language code")
    ap.add_argument("--model", default="gemma2:9b", help="Ollama model name")
    ap.add_argument("--pages", default=None, help="e.g. 1-5 or 3 (1-based)")
    ap.add_argument("--skip-translate", action="store_true",
                    help="reuse an existing translated JSON / cache")
    ap.add_argument("--no-qa", action="store_true", help="skip QA image render")
    ap.add_argument("--out-dir", default="output")
    ap.add_argument("--work-dir", default="work")
    args = ap.parse_args(argv)

    inp = Path(args.input)
    work = Path(args.work_dir)
    out = Path(args.out_dir)
    blocks_path = work / "blocks.json"
    tr_path = work / f"blocks.{args.tgt}.json"
    out_pdf = out / f"{inp.stem}.{args.tgt}.pdf"
    cache_dir = work / "cache"
    pages = parse_pages(args.pages)

    print(f"[1/4] extracting text from {inp} ...")
    extract.run(str(inp), str(blocks_path), source_lang=args.src, target_lang=args.tgt, pages=pages)

    if args.skip_translate and tr_path.exists():
        print(f"[2/4] skip-translate: reusing {tr_path}")
    else:
        print(f"[2/4] translating with Ollama model '{args.model}' ...")

        def prog(done, total):
            print(f"\r    {done}/{total} blocks", end="", flush=True)

        translator = translate.OllamaTranslator(model=args.model, src=args.src, tgt=args.tgt)
        translate.run(str(blocks_path), str(tr_path), model=args.model,
                      cache_dir=str(cache_dir), translator=translator, progress=prog)
        print()

    print(f"[3/4] rebuilding -> {out_pdf}")
    doc = json.loads(tr_path.read_text(encoding="utf-8"))
    rebuild.rebuild_pdf(str(inp), doc, str(out_pdf))

    if args.no_qa:
        print("[4/4] QA render skipped")
    else:
        print(f"[4/4] rendering QA images -> {out / 'qa'}")
        render_qa.run(str(inp), str(out_pdf), str(out / "qa"))

    print(f"Done. Output: {out_pdf}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full test suite**

Run: `pytest -q`
Expected: all tests PASS (about 20).

- [ ] **Step 6: Commit**

```
git add pdftranslate/cli.py tests/test_cli.py
git commit -m "feat: add CLI wiring extract->translate->rebuild->render_qa"
```

---

## Task 8: Ollama setup & smoke test

> This task is run by the orchestrator/user. Installing Ollama may require an
> interactive/elevated shell — if so, run the install yourself in the session
> with the `! <command>` prefix.

**Files:** none (environment setup).

- [ ] **Step 1: Install Ollama**

Run: `winget install --id Ollama.Ollama -e`
(Or download the installer from https://ollama.com/download.)
Then open a NEW shell so the updated PATH is picked up.

- [ ] **Step 2: Verify the CLI and server**

Run: `ollama --version`
Then: `ollama list`
Expected: a version string; `ollama list` returns (possibly empty) without a connection error. If the server isn't running, start it (the desktop app, or `ollama serve` in a separate shell).

- [ ] **Step 3: Pull the translation model**

Run: `ollama pull gemma2:9b`
Expected: download completes; `ollama list` now shows `gemma2:9b`.
(Lighter alternative: `ollama pull gemma2:2b`. Translation-focused alternative: `ollama pull aya-expanse:8b`.)

- [ ] **Step 4: Smoke-test the API endpoint**

Run: `python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:11434/api/tags', timeout=5).status)"`
Expected: `200`.

- [ ] **Step 5: Smoke-test a real translation through our client**

Run:
```
python -c "from pdftranslate.translate import OllamaTranslator; print(OllamaTranslator(model='gemma2:9b', src='en', tgt='no')('Hello, how are you?'))"
```
Expected: a Norwegian sentence (e.g., `Hei, hvordan har du det?`), no errors.

---

## Task 9: Full integration run on the real paper

**Files:** uses `aerospace-10-00563.pdf`; writes `output/` and `work/` (gitignored).

- [ ] **Step 1: Fast partial run (first 2 pages) to sanity-check**

Run: `python -m pdftranslate aerospace-10-00563.pdf --to no --model gemma2:9b --pages 1-2`
Expected: completes the 4 stages; `output/aerospace-10-00563.no.pdf` is created.

- [ ] **Step 2: Visually verify the partial output**

Open `output/qa/original_p1.png` and `output/qa/translated_p1.png` side by side.
Expected: figures/charts identical and present; body text is Norwegian; layout matches.

- [ ] **Step 3: Full run**

Run: `python -m pdftranslate aerospace-10-00563.pdf --to no --model gemma2:9b`
Expected: completes (may take several minutes on first run; cache makes re-runs fast).

- [ ] **Step 4: Verify acceptance criteria programmatically**

Run:
```
python -c "import fitz; a=fitz.open('aerospace-10-00563.pdf'); b=fitz.open('output/aerospace-10-00563.no.pdf'); print('pages', a.page_count, b.page_count); print('match', a.page_count==b.page_count)"
```
Expected: `match True` (same page count).
Also confirm `output/qa/translated_p1.png` … `_p3.png` exist and look correct.

- [ ] **Step 5: Verify warm-cache re-run does no re-translation**

Run: `python -m pdftranslate aerospace-10-00563.pdf --to no --model gemma2:9b --skip-translate`
Expected: stage [2/4] prints "skip-translate: reusing …" and finishes quickly.

- [ ] **Step 6 (optional): Track the sample PDF as a test fixture**

The paper is open-access (MDPI, CC BY), so it can be committed for reproducibility.
```
git add aerospace-10-00563.pdf
git commit -m "test: add aerospace-10-00563.pdf as integration fixture"
```
(Skip this step if you prefer not to track the 7 MB binary.)

---

## Task 10: README & final commit

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

`README.md`:
````markdown
# pdftranslate

Translate a born-digital PDF while keeping its original layout and figures.

It reads each text block with its position, removes only the original text
(figures, charts, and vector graphics are untouched), translates with a local
Ollama model, and inserts the translation back into the same boxes.

## Setup

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Install Ollama (https://ollama.com) and pull a multilingual model:

```
ollama pull gemma2:9b
```

## Usage

```
python -m pdftranslate input.pdf --to no --model gemma2:9b
```

Output: `output/<name>.no.pdf` plus QA images in `output/qa/`.

Useful flags: `--from en`, `--pages 1-5`, `--skip-translate`, `--no-qa`,
`--out-dir`, `--work-dir`.

## How it works

`extract` → `work/blocks.json` → `translate` (Ollama + cache) →
`work/blocks.<lang>.json` → `rebuild` → `output/<name>.<lang>.pdf` → `render_qa`.

## Known limitations (v1)

- Born-digital PDFs only (no OCR for scanned pages).
- Typeface/bold/italic not reproduced — text is re-inserted in one embedded font.
- Inline equations are skipped (left as original).
- Assumes a white page background.

See `docs/specs/` and `docs/plans/` for the design and plan.
````

- [ ] **Step 2: Run the full suite once more**

Run: `pytest -q`
Expected: all PASS.

- [ ] **Step 3: Commit**

```
git add README.md
git commit -m "docs: add README with setup, usage, and limitations"
```

---

## Acceptance criteria (from the spec)

1. `python -m pdftranslate aerospace-10-00563.pdf --to no` runs end-to-end with no errors (Ollama up + model pulled).
2. `output/aerospace-10-00563.no.pdf` opens, has the same page count, figures visibly present and unchanged.
3. Body text in the output is Norwegian.
4. QA PNGs show original vs translated with figures intact.
5. A warm-cache / `--skip-translate` re-run does no re-translation and is fast.
6. `pytest -q` passes: extract produces contract-valid JSON; translate works with a mock; rebuild produces a valid PDF from a fixture.
