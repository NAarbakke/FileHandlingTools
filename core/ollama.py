"""Shared Ollama chat client used by every tool (translate, transcribe, cleanup).

One place for the raw-HTTP call to the local Ollama `/api/chat` endpoint, so each
per-tool callable only has to build its messages and pick a temperature.
"""
from __future__ import annotations

import json
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"


def chat(model, messages, *, url=OLLAMA_URL, temperature=0.0, timeout=300):
    """POST a chat completion to Ollama and return the stripped reply text.

    `messages` is the standard list of {role, content[, images]} dicts; vision
    transcription passes base64-encoded PNGs in a user message's `images` field.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["message"]["content"].strip()
