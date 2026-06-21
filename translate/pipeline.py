"""End-to-end translate pipeline: extract -> translate -> rebuild -> render_qa.

The tool's public entry point, called by the unified TUI and by tests. The model
default resolves from the shared `core/models.json` via `core.modelmap`; a
`translator` can be injected to run without a live Ollama server.
"""
from __future__ import annotations

import json
from pathlib import Path

from core import modelmap
from core.pages import parse_pages

from . import extract, translate, rebuild, render_qa

__all__ = ["pipeline", "parse_pages"]


def pipeline(input_path, *, src="en", tgt="no", model=None, pages=None,
             skip_translate=False, no_qa=False, out_dir="output", work_dir="work",
             translator=None, log=None, progress=None):
    """Translate `input_path` and rebuild it, keeping layout/figures. Returns the output path.

    `pages` may be a set of 0-based indices or a spec string like "1-5".
    """
    say = log or (lambda *_: None)
    if isinstance(pages, str):
        pages = parse_pages(pages)
    model = model or modelmap.get_model("translate", "translate", "gemma2:2b")

    inp = Path(input_path)
    work = Path(work_dir)
    out = Path(out_dir)
    blocks_path = work / "blocks.json"
    tr_path = work / f"blocks.{tgt}.json"
    out_pdf = out / f"{inp.stem}.{tgt}.pdf"
    cache_dir = work / "cache"

    say(f"[1/4] extracting text from {inp} ...")
    extract.run(str(inp), str(blocks_path), source_lang=src, target_lang=tgt, pages=pages)

    if skip_translate and tr_path.exists():
        say(f"[2/4] skip-translate: reusing {tr_path}")
    else:
        say(f"[2/4] translating with Ollama model '{model}' ...")
        if translator is None:
            translator = translate.OllamaTranslator(model=model, src=src, tgt=tgt)
        translate.run(str(blocks_path), str(tr_path), model=model,
                      cache_dir=str(cache_dir), translator=translator, progress=progress)
        say("")

    say(f"[3/4] rebuilding -> {out_pdf}")
    doc = json.loads(tr_path.read_text(encoding="utf-8"))
    rebuild.rebuild_pdf(str(inp), doc, str(out_pdf))

    if no_qa:
        say("[4/4] QA render skipped")
    else:
        say(f"[4/4] rendering QA images -> {out / 'qa'}")
        render_qa.run(str(inp), str(out_pdf), str(out / "qa"))

    say(f"Done. Output: {out_pdf}")
    return out_pdf
