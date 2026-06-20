"""translate pipeline + thin argparse entry: extract -> translate -> rebuild -> render_qa.

`pipeline()` is the public entry point (used by the unified TUI and tests); `main()` is a
back-compatible argparse wrapper around it. Model defaults resolve from `models.json`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import extract, translate, rebuild, render_qa

# Make the repo-root shared model mapper importable regardless of CWD.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
import modelmap  # noqa: E402


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


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="translate",
        description="Translate a PDF while keeping its layout and figures.",
    )
    ap.add_argument("input", help="input PDF path")
    ap.add_argument("--from", dest="src", default="en", help="source language code")
    ap.add_argument("--to", dest="tgt", default="no", help="target language code")
    ap.add_argument("--model", default=modelmap.get_model("translate", "translate", "gemma2:2b"),
                    help="Ollama model name (default from models.json)")
    ap.add_argument("--pages", default=None, help="e.g. 1-5 or 3 (1-based)")
    ap.add_argument("--skip-translate", action="store_true",
                    help="reuse an existing translated JSON / cache")
    ap.add_argument("--no-qa", action="store_true", help="skip QA image render")
    ap.add_argument("--out-dir", default="output")
    ap.add_argument("--work-dir", default="work")
    args = ap.parse_args(argv)

    def prog(done, total):
        print(f"\r    {done}/{total} blocks", end="", flush=True)

    pipeline(args.input, src=args.src, tgt=args.tgt, model=args.model,
             pages=parse_pages(args.pages), skip_translate=args.skip_translate,
             no_qa=args.no_qa, out_dir=args.out_dir, work_dir=args.work_dir,
             log=print, progress=prog)


if __name__ == "__main__":
    main()
