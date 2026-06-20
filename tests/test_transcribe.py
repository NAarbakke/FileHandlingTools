import base64
import json
import urllib.request

from transcribe import transcribe


def make_manifest(img):
    return {"source": "x.png", "dpi": 200, "page_count": 1,
            "pages": [{"page": 1, "image": img}]}


def test_transcribes_each_page():
    m = make_manifest("a.png")
    transcribe.transcribe_document(m, transcriber=lambda p: f"MD:{p}")
    assert m["pages"][0]["markdown"] == "MD:a.png"


def test_cache_avoids_second_call(tiny_png, tmp_path):
    calls = {"n": 0}

    def tr(p):
        calls["n"] += 1
        return "# x"

    cache = str(tmp_path / "cache")
    transcribe.transcribe_document(make_manifest(tiny_png), tr, cache_dir=cache)
    transcribe.transcribe_document(make_manifest(tiny_png), tr, cache_dir=cache)
    assert calls["n"] == 1  # second run served from cache


def test_cache_key_depends_on_model_and_image(tiny_png):
    k1 = transcribe.cache_key("m1", tiny_png)
    k2 = transcribe.cache_key("m1", tiny_png)
    k3 = transcribe.cache_key("m2", tiny_png)
    assert k1 == k2 != k3


def test_run_writes_markdown_json(tiny_png, tmp_path):
    manifest_path = tmp_path / "pages.json"
    manifest_path.write_text(json.dumps(make_manifest(tiny_png)), encoding="utf-8")
    out = tmp_path / "transcript.json"
    transcribe.run(str(manifest_path), str(out), transcriber=lambda p: "# Title")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["pages"][0]["markdown"] == "# Title"


def test_ollama_transcriber_sends_base64_image_and_parses_response(tiny_png, monkeypatch):
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
        return FakeResp(json.dumps({"message": {"content": "  # Note\n"}}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    out = transcribe.OllamaTranscriber(model="qwen2.5vl:3b")(tiny_png)

    assert out == "# Note"  # response is stripped
    assert captured["payload"]["model"] == "qwen2.5vl:3b"
    msg = captured["payload"]["messages"][-1]
    assert len(msg["images"]) == 1
    with open(tiny_png, "rb") as fh:
        assert base64.b64decode(msg["images"][0]) == fh.read()
