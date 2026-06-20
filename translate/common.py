"""Shared helpers: color conversion and the non-prose skip heuristic."""
from __future__ import annotations

import re

_LETTER_RE = re.compile(r"[A-Za-zÀ-ÿ]")


def color_int_to_rgb(color):
    """Convert a PyMuPDF sRGB integer to an (r, g, b) tuple of 0..1 floats."""
    if color is None:
        return (0.0, 0.0, 0.0)
    r = (color >> 16) & 255
    g = (color >> 8) & 255
    b = color & 255
    return (r / 255.0, g / 255.0, b / 255.0)


def looks_untranslatable(text):
    """True if a block is non-prose (blank, bare number, equation, symbols).

    Such blocks are left exactly as the original: not translated, not redacted.
    Errs toward translating — only short, letter-poor blocks are skipped.
    """
    stripped = text.strip()
    if not stripped:
        return True
    letters = len(_LETTER_RE.findall(stripped))
    if letters == 0:
        return True
    letter_ratio = letters / len(stripped)
    if letter_ratio < 0.4 and len(stripped) < 60:
        return True
    return False
