import tui


def feeder(values):
    """Return an input_fn that yields queued answers in order."""
    it = iter(values)
    return lambda prompt="": next(it)


def test_clean_strips_bom_and_whitespace():
    assert tui._clean("  2  ") == "2"
    assert tui._clean(chr(0xFEFF) + "0") == "0"      # real BOM (U+FEFF)
    assert tui._clean("\xef\xbb\xbf0") == "0"        # UTF-8 BOM byte-wise (Windows cp1252 stdin)


def test_menu_shows_tools_and_quits():
    out = []
    tui.run(tools=[], input_fn=feeder(["0"]), output_fn=out.append)
    joined = "\n".join(out)
    assert "FileHandlingTools" in joined
    assert any("bye" in line for line in out)


def test_menu_dispatches_to_selected_tool():
    called = []
    tools = [{"key": "1", "label": "x", "desc": "d", "run": lambda i, o: called.append("ran")}]
    tui.run(tools=tools, input_fn=feeder(["1", "0"]), output_fn=lambda *_: None)
    assert called == ["ran"]


def test_invalid_choice_keeps_menu_alive():
    out = []
    tools = [{"key": "1", "label": "x", "desc": "d", "run": lambda i, o: None}]
    tui.run(tools=tools, input_fn=feeder(["9", "0"]), output_fn=out.append)
    assert any("invalid" in line.lower() for line in out)


def test_tool_error_does_not_crash_menu():
    def boom(i, o):
        raise RuntimeError("kaboom")

    out = []
    tools = [{"key": "1", "label": "x", "desc": "d", "run": boom}]
    tui.run(tools=tools, input_fn=feeder(["1", "0"]), output_fn=out.append)
    assert any("kaboom" in line for line in out)


def test_transcribe_runner_invokes_pipeline(monkeypatch):
    from tools import transcribe
    captured = {}
    monkeypatch.setattr(transcribe, "pipeline",
                        lambda src, **kw: captured.update(src=src, **kw) or {"md": "output/x.md"})

    tui.run_transcribe(feeder(["notes.jpg", "md,pdf", "n", "", "output"]), lambda *_: None)
    assert captured["src"] == "notes.jpg"
    assert captured["formats"] == "md,pdf"
    assert captured["cleanup"] is False


def test_translate_runner_invokes_pipeline(monkeypatch):
    from tools import translate
    captured = {}

    def fake(input_path, **kw):
        captured["input"] = input_path
        captured.update(kw)

    monkeypatch.setattr(translate, "pipeline", fake)

    tui.run_translate(feeder(["paper.pdf", "no", "en", "", "output"]), lambda *_: None)
    assert captured["input"] == "paper.pdf"
    assert captured["tgt"] == "no"   # target language
    assert captured["src"] == "en"   # source language


def test_convert_runner_writes_to_output_dir(tiny_pdf, tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(tui, "INPUT_DIR", tmp_path / "noinput")  # empty -> path prompt
    out_dir = tmp_path / "out"
    monkeypatch.setattr(tui, "OUTPUT_DIR", out_dir)
    out = []
    tui.run_convert(feeder([tiny_pdf, "txt"]), out.append)
    produced = out_dir / (Path(tiny_pdf).stem + ".txt")
    assert produced.exists()
    assert "Hello world" in produced.read_text(encoding="utf-8")
    assert any("wrote" in line for line in out)


def test_convert_runner_rejects_unsupported_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr(tui, "INPUT_DIR", tmp_path / "noinput")
    bad = tmp_path / "data.csv"
    bad.write_text("x", encoding="utf-8")
    out = []
    tui.run_convert(feeder([str(bad)]), out.append)
    assert any("unsupported" in line.lower() for line in out)


def test_convert_is_registered_in_tools():
    labels = [t["label"] for t in tui.TOOLS]
    assert "convert" in labels


def test_pick_input_lists_and_picks_by_number(tmp_path, monkeypatch):
    (tmp_path / "a.pdf").write_text("", encoding="utf-8")
    (tmp_path / "b.pdf").write_text("", encoding="utf-8")
    monkeypatch.setattr(tui, "INPUT_DIR", tmp_path)
    got = tui._pick_input(feeder(["2"]), lambda *_: None, "input", {".pdf"})
    assert got == str(tmp_path / "b.pdf")


def test_pick_input_accepts_custom_path_when_typed(tmp_path, monkeypatch):
    (tmp_path / "a.pdf").write_text("", encoding="utf-8")
    monkeypatch.setattr(tui, "INPUT_DIR", tmp_path)
    got = tui._pick_input(feeder(["/some/where/custom.pdf"]), lambda *_: None, "input", {".pdf"})
    assert got == "/some/where/custom.pdf"


def test_pick_input_falls_through_when_dir_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(tui, "INPUT_DIR", tmp_path / "empty")
    got = tui._pick_input(feeder(["typed.pdf"]), lambda *_: None, "input", {".pdf"})
    assert got == "typed.pdf"
