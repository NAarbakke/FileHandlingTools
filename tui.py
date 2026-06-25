"""FileHandlingTools — one terminal menu to run every tool in the project.

Run:  python tui.py

Lean stdlib UI: a numbered menu plus input() prompts. Each tool exposes a
`pipeline()` function; the per-tool runners below gather inputs and call it.
To add a tool: write a `run_<tool>()` and append an entry to TOOLS.
"""
from __future__ import annotations

from pathlib import Path

import translate
import transcribe

INPUT_DIR = Path("input")    # default location for source documents
OUTPUT_DIR = Path("output")  # where convert writes when run from the menu

# Suffixes used to list candidate files in input/ for each tool's picker.
_PDF_EXTS = {".pdf"}
_IMAGE_PDF_EXTS = _PDF_EXTS | {
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp", ".pnm", ".ppm",
}
_CONVERT_EXTS = _PDF_EXTS | {".docx", ".pptx"}

# A UTF-8 BOM can lead piped/redirected input: as U+FEFF, or — when stdin is read
# under a byte-wise codec (Windows cp1252) — as the three chars '\xef\xbb\xbf'.
_BOMS = (chr(0xFEFF), "\xef\xbb\xbf")


def _clean(s):
    s = s.strip()
    for bom in _BOMS:
        if s.startswith(bom):
            return s[len(bom):].strip()
    return s


def _ask(input_fn, label, default=None):
    suffix = f" [{default}]" if default else ""
    val = _clean(input_fn(f"  {label}{suffix}: "))
    return val or (default or "")


def _ask_yesno(input_fn, label, default=False):
    val = _clean(input_fn(f"  {label} [{'Y/n' if default else 'y/N'}]: ")).lower()
    if not val:
        return default
    return val in ("y", "yes")


def _pick_input(input_fn, output_fn, label, exts):
    """Choose an input file: pick one listed in input/, or type any path.

    Lists files in INPUT_DIR whose suffix is in `exts`; the user enters a list
    number to pick one, or types a path to use a file from anywhere. Returns the
    chosen path as a string ('' if cancelled).
    """
    files = []
    if INPUT_DIR.is_dir():
        files = sorted(p for p in INPUT_DIR.iterdir()
                       if p.is_file() and p.suffix.lower() in exts)
    if files:
        output_fn(f"  files in {INPUT_DIR}/:")
        for i, p in enumerate(files, 1):
            output_fn(f"    {i}) {p.name}")
        ans = _ask(input_fn, f"{label} — number above, or a path", "1")
        if ans.isdigit() and 1 <= int(ans) <= len(files):
            return str(files[int(ans) - 1])
        return ans  # anything that isn't a list number is treated as a path
    return _ask(input_fn, f"{label} (path)")


def run_translate(input_fn, output_fn):
    src = _pick_input(input_fn, output_fn, "input PDF", _PDF_EXTS)
    if not src:
        output_fn("  (no input — cancelled)")
        return
    tgt = _ask(input_fn, "target language", "no")
    frm = _ask(input_fn, "source language", "en")
    pages = _ask(input_fn, "pages (e.g. 1-5, blank=all)") or None
    out_dir = _ask(input_fn, "out dir", "output")
    translate.pipeline(
        src, src=frm, tgt=tgt, pages=pages, out_dir=out_dir,
        log=output_fn, progress=lambda d, t: output_fn(f"    {d}/{t} blocks"),
    )


def run_transcribe(input_fn, output_fn):
    src = _pick_input(input_fn, output_fn, "input image/PDF", _IMAGE_PDF_EXTS)
    if not src:
        output_fn("  (no input — cancelled)")
        return
    formats = _ask(input_fn, "formats", "md")
    cleanup = _ask_yesno(input_fn, "cleanup pass?", False)
    pages = _ask(input_fn, "pages (PDF; blank=all)") or None
    out_dir = _ask(input_fn, "out dir", "output")
    written = transcribe.pipeline(
        src, formats=formats, cleanup=cleanup, pages=pages, out_dir=out_dir,
        log=output_fn, progress=lambda d, t: output_fn(f"    {d}/{t} pages"),
    )
    output_fn("  wrote: " + ", ".join(written.values()))


def run_convert(input_fn, output_fn):
    # Imported lazily so launching the menu doesn't load the convert deps
    # (pymupdf4llm / markitdown).
    from convert import common, docx_to_md, pdf_to_md, pdf_to_txt, pptx_to_md

    src = _pick_input(input_fn, output_fn, "input file (pdf/docx/pptx)", _CONVERT_EXTS)
    if not src:
        output_fn("  (no input — cancelled)")
        return

    suf = Path(src).suffix.lower()
    if suf == ".pdf":
        fmt = _ask(input_fn, "format (md/txt)", "md").lower()
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

    out_path = OUTPUT_DIR / (Path(src).stem + out_suffix)
    common.write_output(fn(src), out_path)
    output_fn(f"  wrote: {out_path}")


TOOLS = [
    {"key": "1", "label": "translate", "desc": "translate a PDF, keep layout", "run": run_translate},
    {"key": "2", "label": "transcribe", "desc": "handwritten notes -> md/txt/docx/pdf", "run": run_transcribe},
    {"key": "3", "label": "convert", "desc": "pdf/docx/pptx -> md/txt", "run": run_convert},
]


def _print_menu(tools, output_fn):
    output_fn("")
    output_fn("FileHandlingTools")
    output_fn("=================")
    for t in tools:
        output_fn(f" {t['key']}) {t['label']:<12} {t['desc']}")
    output_fn(" 0) quit")


def run(tools=None, input_fn=input, output_fn=print):
    tools = TOOLS if tools is None else tools
    by_key = {t["key"]: t for t in tools}
    while True:
        _print_menu(tools, output_fn)
        choice = _clean(input_fn("Select a tool [1]: ")) or "1"
        if choice in ("0", "q", "quit"):
            output_fn("bye")
            return
        tool = by_key.get(choice)
        if tool is None:
            output_fn(f"  invalid choice: {choice!r}")
            continue
        try:
            tool["run"](input_fn, output_fn)
        except Exception as e:  # keep the menu alive if a tool fails
            output_fn(f"  error: {e}")


if __name__ == "__main__":
    try:
        run()
    except (KeyboardInterrupt, EOFError):
        print()
