"""Stage 2: transcribe each page image to Markdown via a local Ollama vision model.

Mirrors translate's translate stage: a monkeypatch-friendly callable backed by a
raw-HTTP Ollama client, plus an on-disk cache so re-runs don't re-call the VLM.
The prompt is deliberately *verbatim*: transcribe exactly, never translate or reword.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from core import ollama

SYSTEM_PROMPT = (
    "You are a careful transcriber of handwritten notes. "
    "Transcribe ALL handwritten and printed text in the image exactly as written. "
    "Output GitHub-Flavored Markdown: use '#' headings, '-' bullets, and '1.' numbered "
    "lists to mirror the page's structure and reading order. "
    "Do NOT translate, summarize, correct, or add commentary. "
    "Preserve the original language(s), spelling, numbers, units, and symbols. "
    "Mark anything you cannot read as [illegible]. "
    "Output ONLY the transcription, with no preamble and no surrounding code fences."
)


def _b64_image(path):
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


class OllamaTranscriber:
    """Callable transcriber backed by a local Ollama vision (VLM) chat model."""

    def __init__(self, model="qwen2.5vl:3b", url=ollama.OLLAMA_URL, temperature=0.1, timeout=600):
        self.model = model
        self.url = url
        self.temperature = temperature
        self.timeout = timeout
        self.system = SYSTEM_PROMPT

    def __call__(self, image_path):
        messages = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": "Transcribe this page.",
             "images": [_b64_image(image_path)]},
        ]
        return ollama.chat(self.model, messages, url=self.url,
                           temperature=self.temperature, timeout=self.timeout)


def cache_key(model, image_path):
    """Stable key over (model, prompt, image bytes) so edits to any invalidate it."""
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(SYSTEM_PROMPT.encode("utf-8"))
    h.update(b"\x00")
    h.update(Path(image_path).read_bytes())
    return h.hexdigest()


def transcribe_document(manifest, transcriber, cache_dir=None, progress=None):
    """Add `markdown` to every page in `manifest`. Mutates and returns `manifest`."""
    model = getattr(transcriber, "model", "mock")
    cache = Path(cache_dir) if cache_dir else None
    if cache:
        cache.mkdir(parents=True, exist_ok=True)

    pages = manifest["pages"]
    total = len(pages)
    for done, page in enumerate(pages, start=1):
        img = page["image"]
        cfile = cache / f"{cache_key(model, img)}.md" if cache else None
        if cfile is not None and cfile.exists():
            md = cfile.read_text(encoding="utf-8")
        else:
            md = transcriber(img)
            if cfile is not None:
                cfile.write_text(md, encoding="utf-8")
        page["markdown"] = md
        if progress:
            progress(done, total)
    manifest["model"] = model
    return manifest


def run(manifest_path, out_path, *, model="qwen2.5vl:3b", cache_dir=None,
        transcriber=None, progress=None):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if transcriber is None:
        transcriber = OllamaTranscriber(model=model)
    transcribe_document(manifest, transcriber, cache_dir=cache_dir, progress=progress)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
