"""Reference model mapper: one source of truth for which Ollama model each tool uses.

Edit `models.json` (next to this file) to change which model a tool/role runs on.
Both `translate` and `transcribe` read their default model from here, so models are
configured in one place. An explicit `model=` argument to a tool's pipeline() overrides it.

Resolution order for get_model(tool, role):
    1. env var OLLAMA_MODEL_<TOOL>_<ROLE>  (e.g. OLLAMA_MODEL_TRANSCRIBE_TRANSCRIBE)
    2. models.json
    3. the `default` argument
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "models.json"


def _load():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def get_model(tool, role, default=None):
    """Return the configured Ollama model name for a tool/role (see module docstring)."""
    env_key = f"OLLAMA_MODEL_{tool}_{role}".upper().replace("-", "_").replace(".", "_")
    if env_key in os.environ:
        return os.environ[env_key]
    return _load().get(tool, {}).get(role, default)
