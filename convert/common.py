"""Shared CLI runner and IO helpers for the convert/ scripts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def check_suffix(in_path, allowed):
    """Raise ValueError if in_path's suffix isn't in `allowed` (lowercased exts)."""
    suf = Path(in_path).suffix.lower()
    if suf not in allowed:
        allowed_str = ", ".join(sorted(allowed))
        raise ValueError(
            f"{Path(in_path).name}: expected one of {allowed_str}, got {suf or '(none)'}"
        )


def resolve_out(in_path, out_suffix):
    """Default output path: sibling of input, same stem, with `out_suffix`."""
    return Path(in_path).with_suffix(out_suffix)


def write_output(text, out_path):
    """Write `text` as UTF-8 to `out_path`, creating parent dirs. Return the Path."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def cli(convert_fn, *, in_suffixes, out_suffix, description, argv=None):
    """Parse args, convert one or more inputs, write outputs. Return written paths."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("inputs", nargs="+", help="input file(s)")
    parser.add_argument("-o", "--out", help="output path (single input only)")
    args = parser.parse_args(argv)

    if args.out and len(args.inputs) > 1:
        parser.error("-o/--out is only valid with a single input file")

    written = []
    for in_path in args.inputs:
        src = Path(in_path)
        if not src.exists():
            print(f"error: no such file: {in_path}", file=sys.stderr)
            raise SystemExit(1)
        try:
            check_suffix(src, in_suffixes)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            raise SystemExit(1)
        try:
            text = convert_fn(src)
        except Exception as e:  # surface a readable conversion failure
            print(f"error: failed to convert {in_path}: {e}", file=sys.stderr)
            raise SystemExit(1)
        out_path = Path(args.out) if args.out else resolve_out(src, out_suffix)
        write_output(text, out_path)
        print(f"wrote {out_path}")
        written.append(out_path)
    return written


def markitdown_to_md(in_path):
    """Convert a docx/pptx file to Markdown via markitdown."""
    from markitdown import MarkItDown

    result = MarkItDown().convert(str(in_path))
    return result.text_content
