"""Tests for the optional OpenAI-compatible client (core.openai_compat).

No network: urllib.request.urlopen is monkeypatched, as in test_transcribe.py.
"""
import base64
import json
import urllib.request

from core import openai_compat


class _FakeResp:
    def __init__(self, body):
        self._b = body

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch(monkeypatch, reply="  hi there\n"):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.headers)
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp(json.dumps({"choices": [{"message": {"content": reply}}]}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return captured


def test_chat_posts_openai_shape_and_strips_reply(monkeypatch):
    captured = _patch(monkeypatch)
    out = openai_compat.chat("llama3", [{"role": "user", "content": "hey"}],
                             base_url="http://example:1234/v1")
    assert out == "hi there"  # response stripped, parsed from choices[0]
    assert captured["url"] == "http://example:1234/v1/chat/completions"
    assert captured["payload"]["model"] == "llama3"
    assert captured["payload"]["stream"] is False


def test_api_key_sets_bearer_header(monkeypatch):
    captured = _patch(monkeypatch)
    openai_compat.chat("m", [{"role": "user", "content": "x"}], api_key="secret-123")
    # urllib title-cases header keys
    assert captured["headers"]["Authorization"] == "Bearer secret-123"


def test_no_api_key_means_no_auth_header(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured = _patch(monkeypatch)
    openai_compat.chat("m", [{"role": "user", "content": "x"}])
    assert "Authorization" not in captured["headers"]


def test_base_url_defaults_to_env(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://env-host:9/v1")
    # module read the env at import time; patch the module constant to simulate
    monkeypatch.setattr(openai_compat, "OPENAI_BASE_URL", "http://env-host:9/v1")
    captured = _patch(monkeypatch)
    openai_compat.chat("m", [{"role": "user", "content": "x"}])
    assert captured["url"] == "http://env-host:9/v1/chat/completions"


def test_image_message_builds_data_uri_part(tiny_png):
    msg = openai_compat.image_message("Transcribe this.", tiny_png)
    assert msg["role"] == "user"
    text_part, image_part = msg["content"]
    assert text_part == {"type": "text", "text": "Transcribe this."}
    url = image_part["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    decoded = base64.b64decode(url.split(",", 1)[1])
    with open(tiny_png, "rb") as fh:
        assert decoded == fh.read()
