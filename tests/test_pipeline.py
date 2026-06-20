from pathlib import Path

import transcribe


def test_parse_pages():
    assert transcribe.parse_pages(None) is None
    assert transcribe.parse_pages("3") == {2}
    assert transcribe.parse_pages("1-3") == {0, 1, 2}
    assert transcribe.parse_pages("1-2,5") == {0, 1, 4}


def test_pipeline_end_to_end_with_injected_transcriber(tiny_png, tmp_path):
    written = transcribe.pipeline(
        tiny_png,
        formats=["md", "txt", "docx", "pdf"],
        out_dir=str(tmp_path / "output"),
        work_dir=str(tmp_path / "work"),
        transcriber=lambda img: "# Note\n\nbody text",
    )
    assert set(written) == {"md", "txt", "docx", "pdf"}
    stem = Path(tiny_png).stem
    for ext in ["md", "txt", "docx", "pdf"]:
        assert (tmp_path / "output" / f"{stem}.{ext}").exists()
    assert (tmp_path / "work" / "transcript.json").exists()
    assert "Note" in (tmp_path / "output" / f"{stem}.md").read_text(encoding="utf-8")


def test_pipeline_default_model_comes_from_mapper(tiny_png, tmp_path, monkeypatch):
    import modelmap
    monkeypatch.setattr(modelmap, "get_model", lambda *a, **k: "SENTINEL:vlm")

    captured = {}
    import transcribe.transcribe as T
    monkeypatch.setattr(T, "OllamaTranscriber",
                        lambda **kw: captured.update(kw) or (lambda img: "x"))

    transcribe.pipeline(tiny_png, out_dir=str(tmp_path / "o"), work_dir=str(tmp_path / "w"))
    assert captured["model"] == "SENTINEL:vlm"


def test_pipeline_cleanup_uses_injected_cleaner(tiny_png, tmp_path):
    written = transcribe.pipeline(
        tiny_png,
        formats=["md"],
        out_dir=str(tmp_path / "output"),
        work_dir=str(tmp_path / "work"),
        cleanup=True,
        transcriber=lambda img: "raw text",
        cleaner=lambda md: "CLEANED",
    )
    assert "CLEANED" in Path(written["md"]).read_text(encoding="utf-8")
