"""Corrected public native-function rewrite entry."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_function import rewrite_generated_function as _rewrite


def rewrite_generated_function(path: Path) -> Path:
    _rewrite(path)
    source = path.read_text(encoding="utf-8")
    broken = r'elif char == "\":'
    corrected = r'elif char == "\\":'
    if broken not in source:
        raise ValueError("generated function quote scanner has an unexpected escape")
    path.write_text(source.replace(broken, corrected, 1), encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function"]
