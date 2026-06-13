from pdftranslate import render_qa


def test_render_pages_writes_pngs(tiny_pdf, tmp_path):
    out = tmp_path / "qa"
    paths = render_qa.render_pages(tiny_pdf, str(out), "original", pages=1, dpi=72)
    assert len(paths) == 1
    assert paths[0].exists()
    assert paths[0].name == "original_p1.png"


def test_run_renders_both(tiny_pdf, tmp_path):
    out = tmp_path / "qa"
    render_qa.run(tiny_pdf, tiny_pdf, str(out), pages=1, dpi=72)
    assert (out / "original_p1.png").exists()
    assert (out / "translated_p1.png").exists()
