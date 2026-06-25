import pytest

from convert import common


def test_check_suffix_accepts_allowed():
    common.check_suffix("paper.PDF", {".pdf"})  # case-insensitive, no raise


def test_check_suffix_rejects_disallowed():
    with pytest.raises(ValueError):
        common.check_suffix("paper.txt", {".pdf"})


def test_resolve_out_is_sibling_with_new_suffix(tmp_path):
    src = tmp_path / "report.pdf"
    assert common.resolve_out(src, ".md") == tmp_path / "report.md"


def test_write_output_creates_parents_and_writes_utf8(tmp_path):
    out = tmp_path / "sub" / "dir" / "x.md"
    returned = common.write_output("héllo", out)
    assert returned == out
    assert out.read_text(encoding="utf-8") == "héllo"


def _touch(path, text="data"):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_cli_single_input_writes_sibling(tmp_path):
    src = _touch(tmp_path / "a.pdf")
    written = common.cli(lambda p: "OUT", in_suffixes={".pdf"},
                         out_suffix=".md", description="t", argv=[src])
    assert written == [tmp_path / "a.md"]
    assert (tmp_path / "a.md").read_text(encoding="utf-8") == "OUT"


def test_cli_multiple_inputs_each_write_sibling(tmp_path):
    a = _touch(tmp_path / "a.pdf")
    b = _touch(tmp_path / "b.pdf")
    written = common.cli(lambda p: "X", in_suffixes={".pdf"},
                         out_suffix=".md", description="t", argv=[a, b])
    assert set(written) == {tmp_path / "a.md", tmp_path / "b.md"}


def test_cli_out_flag_with_single_input(tmp_path):
    src = _touch(tmp_path / "a.pdf")
    dst = tmp_path / "custom.md"
    common.cli(lambda p: "X", in_suffixes={".pdf"}, out_suffix=".md",
               description="t", argv=[src, "-o", str(dst)])
    assert dst.read_text(encoding="utf-8") == "X"


def test_cli_out_flag_with_multiple_inputs_errors(tmp_path):
    a = _touch(tmp_path / "a.pdf")
    b = _touch(tmp_path / "b.pdf")
    with pytest.raises(SystemExit):
        common.cli(lambda p: "X", in_suffixes={".pdf"}, out_suffix=".md",
                   description="t", argv=[a, b, "-o", "x.md"])


def test_cli_missing_file_errors(tmp_path):
    with pytest.raises(SystemExit):
        common.cli(lambda p: "X", in_suffixes={".pdf"}, out_suffix=".md",
                   description="t", argv=[str(tmp_path / "nope.pdf")])


def test_cli_wrong_suffix_errors(tmp_path):
    src = _touch(tmp_path / "a.txt")
    with pytest.raises(SystemExit):
        common.cli(lambda p: "X", in_suffixes={".pdf"}, out_suffix=".md",
                   description="t", argv=[src])


def test_cli_conversion_failure_exits(tmp_path):
    src = _touch(tmp_path / "a.pdf")

    def boom(p):
        raise RuntimeError("nope")

    with pytest.raises(SystemExit):
        common.cli(boom, in_suffixes={".pdf"}, out_suffix=".md",
                   description="t", argv=[src])
