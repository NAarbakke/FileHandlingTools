from pathlib import Path

from tools import translate


def test_parse_pages():
    assert translate.parse_pages(None) is None
    assert translate.parse_pages("3") == {2}
    assert translate.parse_pages("1-2,5") == {0, 1, 4}


def test_pipeline_end_to_end_with_injected_translator(tiny_pdf, tmp_path):
    out_pdf = translate.pipeline(
        tiny_pdf, tgt="no", no_qa=True,
        out_dir=str(tmp_path / "output"),
        work_dir=str(tmp_path / "work"),
        translator=lambda t: f"NO:{t}",
    )
    stem = Path(tiny_pdf).stem
    assert Path(out_pdf).exists()
    assert (tmp_path / "output" / f"{stem}.no.pdf").exists()
    assert (tmp_path / "work" / "blocks.json").exists()
    assert (tmp_path / "work" / "blocks.no.json").exists()


def test_pipeline_default_model_comes_from_mapper(tiny_pdf, tmp_path, monkeypatch):
    from core import modelmap
    monkeypatch.setattr(modelmap, "get_model", lambda *a, **k: "SENTINEL:model")

    captured = {}
    import tools.translate.translate as T
    monkeypatch.setattr(T, "OllamaTranslator",
                        lambda **kw: captured.update(kw) or (lambda t: f"NO:{t}"))

    translate.pipeline(tiny_pdf, no_qa=True,
                       out_dir=str(tmp_path / "o"), work_dir=str(tmp_path / "w"))
    assert captured["model"] == "SENTINEL:model"
