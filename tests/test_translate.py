from tools.translate import translate


def make_doc():
    return {
        "source_pdf": "x.pdf",
        "source_lang": "en",
        "target_lang": "no",
        "page_count": 1,
        "pages": [{
            "page": 0, "width": 300, "height": 200, "blocks": [
                {"id": "p0_b0", "bbox": [0, 0, 10, 10], "text": "Hello",
                 "size": 12, "color": 0, "skip": False, "skip_reason": None},
                {"id": "p0_b1", "bbox": [0, 0, 10, 10], "text": "12",
                 "size": 12, "color": 0, "skip": True, "skip_reason": "non-prose"},
            ],
        }],
    }


def test_translates_non_skip_only():
    doc = make_doc()
    translate.translate_document(doc, translator=lambda t: f"[NO]{t}")
    b0, b1 = doc["pages"][0]["blocks"]
    assert b0["text_translated"] == "[NO]Hello"
    assert "text_translated" not in b1  # skipped blocks are left alone


def test_cache_avoids_second_call(tmp_path):
    calls = {"n": 0}

    def tr(t):
        calls["n"] += 1
        return f"[NO]{t}"

    cache = str(tmp_path / "cache")
    translate.translate_document(make_doc(), translator=tr, cache_dir=cache)
    translate.translate_document(make_doc(), translator=tr, cache_dir=cache)
    assert calls["n"] == 1  # second run is served entirely from cache


def test_cache_key_is_stable():
    k1 = translate.cache_key("m", "en", "no", "Hello")
    k2 = translate.cache_key("m", "en", "no", "Hello")
    k3 = translate.cache_key("m", "en", "no", "Goodbye")
    assert k1 == k2 != k3


def test_run_writes_translated_json(tmp_path):
    import json
    blocks = tmp_path / "blocks.json"
    blocks.write_text(json.dumps(make_doc()), encoding="utf-8")
    out = tmp_path / "blocks.no.json"
    translate.run(str(blocks), str(out), translator=lambda t: f"[NO]{t}")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["pages"][0]["blocks"][0]["text_translated"] == "[NO]Hello"
