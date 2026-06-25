"""End-to-end transcribe pipeline: ingest -> transcribe -> assemble -> render.

This is the tool's public entry point, called by the unified TUI and by tests.
Model defaults are resolved from the shared `core/models.json` via `core.modelmap`;
`transcriber`/`cleaner` can be injected to run without a live Ollama server.
"""
from __future__ import annotations

import json
from pathlib import Path

from core import modelmap
from core.pages import parse_pages

from . import ingest, transcribe, assemble, render

__all__ = ["pipeline", "parse_pages"]


def pipeline(input_path, *, formats=("md",), model=None, cleanup=False, cleanup_model=None,
             dpi=200, gray=False, pages=None, out_dir="output", work_dir="work",
             transcriber=None, cleaner=None, log=None, progress=None):
    """Transcribe `input_path` (image or PDF) into the requested output formats.

    `pages` may be a set of 0-based indices or a spec string like "1-5". Returns the
    {format: path} dict from the render stage.
    """
    say = log or (lambda *_: None)
    if isinstance(pages, str):
        pages = parse_pages(pages)
    model = model or modelmap.get_model("transcribe", "transcribe", "qwen2.5vl:3b")
    cleanup_model = cleanup_model or modelmap.get_model("transcribe", "cleanup", "gemma2:2b")

    work = Path(work_dir)
    manifest_path = work / "pages.json"
    transcribed_path = work / "transcribed.json"
    transcript_path = work / "transcript.json"
    cache_dir = work / "cache"
    formats = [f.strip() for f in formats if f.strip()] if not isinstance(formats, str) \
        else [f.strip() for f in formats.split(",") if f.strip()]

    say(f"[1/4] ingesting {input_path} ...")
    ingest.run(str(input_path), str(manifest_path), str(work / "pages"),
               dpi=dpi, gray=gray, pages=pages)

    say(f"[2/4] transcribing with Ollama VLM '{model}' ...")
    transcribe.run(str(manifest_path), str(transcribed_path), model=model,
                   cache_dir=str(cache_dir), transcriber=transcriber, progress=progress)

    if cleanup:
        say(f"[3/4] tidying with '{cleanup_model}' ...")
    else:
        say("[3/4] assembling transcript (no cleanup)")
    assemble.run(str(transcribed_path), str(transcript_path),
                 cleanup=cleanup, model=cleanup_model, cleaner=cleaner)

    say(f"[4/4] rendering -> {out_dir} {formats}")
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    return render.render(transcript, str(out_dir), Path(input_path).stem, formats)
