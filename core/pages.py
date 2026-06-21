"""Shared page-range parsing used by both tool pipelines."""
from __future__ import annotations


def parse_pages(spec):
    """'1-5' / '3' / '1-2,5' (1-based) -> set of 0-based indices. None if empty."""
    if not spec:
        return None
    result = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            result.update(range(int(a) - 1, int(b)))
        else:
            result.add(int(part) - 1)
    return result
