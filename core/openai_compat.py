"""OpenAI-compatible chat client (optional alternative to `core.ollama`).

Not wired into any tool — kept here for when you want to point the pipelines at a
server that speaks the OpenAI API (`/v1/chat/completions`): LM Studio, llama.cpp's
server, vLLM, Jan, or even Ollama's own OpenAI-compatible endpoint
(`http://localhost:11434/v1`). Mirrors `core.ollama.chat` so it can be dropped in
as an injected callable.

Configuration (both optional, env-overridable):
    OPENAI_BASE_URL   base URL ending in /v1   (default http://localhost:11434/v1)
    OPENAI_API_KEY    bearer token             (omitted if unset — local servers
                                                usually don't need one)

Stdlib only (urllib), same as `core.ollama` — no extra dependency.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from pathlib import Path

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")


def chat(model, messages, *, base_url=None, api_key=None, temperature=0.0, timeout=300):
    """POST a chat completion to an OpenAI-compatible server; return the reply text.

    `messages` is the standard list of {role, content} dicts. For vision, a user
    message's `content` is a list of parts — build it with `image_message()`.
    """
    base = (base_url or OPENAI_BASE_URL).rstrip("/")
    key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
    }
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{base}/chat/completions", data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


def image_message(text, image_path, *, mime="image/png", role="user"):
    """Build an OpenAI vision message: a text part plus a base64 data-URI image part.

    OpenAI-compatible servers expect images inline as `image_url` parts, unlike
    Ollama's top-level `images` list — this helper produces the right shape.
    """
    b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    return {
        "role": role,
        "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ],
    }
