"""FileHandlingTools — one terminal menu to run every tool in the project.

Run:  python tui.py

Lean stdlib UI: a numbered menu plus input() prompts. Each tool exposes a
`pipeline()` function; the per-tool runners below gather inputs and call it.
To add a tool: write a `run_<tool>()` and append an entry to TOOLS.
"""
from __future__ import annotations

import translate
import transcribe

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


def run_translate(input_fn, output_fn):
    src = _ask(input_fn, "input PDF")
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
    src = _ask(input_fn, "input image/PDF")
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


TOOLS = [
    {"key": "1", "label": "translate", "desc": "translate a PDF, keep layout", "run": run_translate},
    {"key": "2", "label": "transcribe", "desc": "handwritten notes -> md/txt/docx/pdf", "run": run_transcribe},
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
