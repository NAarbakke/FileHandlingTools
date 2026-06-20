"""transcribe: turn handwritten notes into digital documents.

Pipeline (mirrors the sibling `translate` tool):
    ingest -> transcribe -> assemble -> render
Each stage writes a JSON checkpoint so later stages can re-run without re-calling
the vision model. The recognition model is a local Ollama VLM; defaults come from
the shared repo-root `models.json` via `modelmap`.

The whole pipeline is exposed as `transcribe.pipeline(...)`, called by the unified
TUI (`tui.py`) and by tests.
"""
from .pipeline import pipeline, parse_pages  # noqa: F401
