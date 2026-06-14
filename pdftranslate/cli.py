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
    ap.add_argument("--model", default="gemma2:2b", help="Ollama model name")
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
