"""Apply asmpython-safe rewrites to the generated native function entry."""
from __future__ import annotations

from pathlib import Path


_REPLACEMENTS = {
    "str(header[0])": "header[0]",
    "str(header[1])": "header[1]",
    "str(call[0])": "call[0]",
    "str(assignment[0])": "assignment[0]",
}


def rewrite_generated_function(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    for old, new in _REPLACEMENTS.items():
        if old not in source:
            raise ValueError(f"generated function entry is missing conversion: {old}")
        source = source.replace(old, new)
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function"]
