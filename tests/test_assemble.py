import json
import urllib.request

from tools.transcribe import assemble


def make_transcript():
    return {
        "source": "n.png", "model": "m",
        "pages": [
            {"page": 1, "image": "a.png", "markdown": "line one\nline two"},
            {"page": 2, "image": "b.png", "markdown": "second page"},
        ],
    }


def test_cleanup_replaces_markdown_and_keeps_raw():
    t = make_transcript()
    assemble.cleanup_document(t, cleaner=lambda md: md.upper())
    assert t["pages"][0]["markdown"] == "LINE ONE\nLINE TWO"
    assert t["pages"][0]["markdown_raw"] == "line one\nline two"


def test_run_without_cleanup_is_passthrough(tmp_path):
    src = tmp_path / "transcribed.json"
    src.write_text(json.dumps(make_transcript()), encoding="utf-8")
    out = tmp_path / "transcript.json"
    assemble.run(str(src), str(out), cleanup=False)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["pages"][0]["markdown"] == "line one\nline two"
    assert "markdown_raw" not in data["pages"][0]


def test_run_with_cleanup_uses_provided_cleaner(tmp_path):
    src = tmp_path / "transcribed.json"
    src.write_text(json.dumps(make_transcript()), encoding="utf-8")
    out = tmp_path / "transcript.json"
    assemble.run(str(src), str(out), cleanup=True, cleaner=lambda md: "CLEAN")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["pages"][0]["markdown"] == "CLEAN"
    assert data["pages"][0]["markdown_raw"] == "line one\nline two"


def test_ollama_cleaner_sends_text_only_and_parses(monkeypatch):
    captured = {}

    class FakeResp:
        def __init__(self, body):
            self._b = body

        def read(self):
            return self._b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return FakeResp(json.dumps({"message": {"content": "  done\n"}}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    out = assemble.OllamaCleaner(model="gemma2:2b")("# raw")
    assert out == "done"
    assert captured["payload"]["model"] == "gemma2:2b"
    assert "images" not in captured["payload"]["messages"][-1]
