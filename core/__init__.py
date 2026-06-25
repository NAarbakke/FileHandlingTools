"""Shared internals for the FileHandlingTools apps.

Houses the things both tools (translate, transcribe) depend on: the model mapper
(`modelmap` + `models.json`), the Ollama chat client (`ollama`), small helpers
(`pages`), and the bundled font under `assets/`.
"""
from pathlib import Path

# Anchored to this package's own location so it resolves wherever core/ lives.
ASSETS = Path(__file__).resolve().parent / "assets"
