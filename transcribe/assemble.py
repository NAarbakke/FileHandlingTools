"""Stage 3: produce the final canonical transcript, with an optional tidy-up pass.

Without `--cleanup` this just passes the transcribed pages through as the canonical
transcript checkpoint. With `--cleanup`, a local text LLM (gemma2:2b by default) tidies
each page's Markdown — fixing line-wrap/formatting artifacts only, never rewording — and
the original is kept under `markdown_raw` for traceability.
"""
from __future__ import annotations

import json
from pathlib import Path

from core import ollama

CLEANUP_SYSTEM = (
    "You tidy a raw transcription of handwritten notes, given as Markdown. "
    "Fix ONLY obvious transcription artifacts: join words split by a hyphen at a line break, "
    "remove stray line wraps inside a paragraph, and normalize Markdown formatting. "
    "Do NOT change wording, spelling of names, numbers, units, or meaning. "
    "Do NOT translate. Do NOT add or remove content. Keep any [illegible] markers. "
    "Output ONLY the cleaned Markdown, with no preamble and no surrounding code fences."
)


class OllamaCleaner:
    """Callable text tidier backed by a local Ollama chat model (no images)."""

    def __init__(self, model="gemma2:2b", url=ollama.OLLAMA_URL, temperature=0.0, timeout=300):
        self.model = model
        self.url = url
        self.temperature = temperature
        self.timeout = timeout
        self.system = CLEANUP_SYSTEM

    def __call__(self, markdown):
        messages = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": markdown},
        ]
        return ollama.chat(self.model, messages, url=self.url,
                           temperature=self.temperature, timeout=self.timeout)


def cleanup_document(transcript, cleaner, progress=None):
    """Tidy each page's Markdown in place, preserving the original as `markdown_raw`."""
    pages = transcript["pages"]
    total = len(pages)
    for done, page in enumerate(pages, start=1):
        raw = page.get("markdown", "")
        page["markdown_raw"] = raw
        page["markdown"] = cleaner(raw)
        if progress:
            progress(done, total)
    transcript["cleanup"] = True
    return transcript


def run(transcript_path, out_path, *, cleanup=False, model="gemma2:2b",
        cleaner=None, progress=None):
    transcript = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
    if cleanup:
        if cleaner is None:
            cleaner = OllamaCleaner(model=model)
        cleanup_document(transcript, cleaner, progress=progress)
    else:
        transcript["cleanup"] = False
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
    return transcript
