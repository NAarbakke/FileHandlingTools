from pdftranslate import cli


def test_parse_pages():
    assert cli.parse_pages(None) is None
    assert cli.parse_pages("3") == {2}
    assert cli.parse_pages("1-3") == {0, 1, 2}
    assert cli.parse_pages("1-2,5") == {0, 1, 4}


def test_cli_end_to_end_with_mock(tiny_pdf, tmp_path, monkeypatch):
    # Replace the Ollama-backed translator with a mock so no server is needed.
    import pdftranslate.translate as T
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
