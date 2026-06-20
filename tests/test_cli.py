from translate import cli


def test_parse_pages():
    assert cli.parse_pages(None) is None
    assert cli.parse_pages("3") == {2}
    assert cli.parse_pages("1-3") == {0, 1, 2}
    assert cli.parse_pages("1-2,5") == {0, 1, 4}


def test_cli_default_model_comes_from_mapper(tiny_pdf, tmp_path, monkeypatch):
    # The default --model must be resolved through the shared model mapper,
    # not hardcoded. Patch the mapper to a sentinel and confirm it flows through.
    import modelmap
    monkeypatch.setattr(modelmap, "get_model", lambda *a, **k: "SENTINEL:model")

    captured = {}
    import translate.translate as T
    monkeypatch.setattr(
        T, "OllamaTranslator",
        lambda **kw: captured.update(kw) or (lambda t: f"NO:{t}"),
    )

    cli.main([tiny_pdf, "--to", "no",
              "--out-dir", str(tmp_path / "o"), "--work-dir", str(tmp_path / "w"),
              "--no-qa"])
    assert captured["model"] == "SENTINEL:model"


def test_cli_end_to_end_with_mock(tiny_pdf, tmp_path, monkeypatch):
    # Replace the Ollama-backed translator with a mock so no server is needed.
    import translate.translate as T
    monkeypatch.setattr(T, "OllamaTranslator", lambda **kw: (lambda t: f"NO:{t}"))

    out_dir = tmp_path / "output"
    work_dir = tmp_path / "work"
    cli.main([tiny_pdf, "--to", "no",
              "--out-dir", str(out_dir), "--work-dir", str(work_dir), "--no-qa"])

    import os
    stem = os.path.splitext(os.path.basename(tiny_pdf))[0]
    assert (out_dir / f"{stem}.no.pdf").exists()
    assert (work_dir / "blocks.json").exists()
    assert (work_dir / "blocks.no.json").exists()
