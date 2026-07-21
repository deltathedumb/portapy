"""Finalize marker-aware generated function parameters safely."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_function_parameter_kinds import (
    rewrite_generated_function_parameter_kinds as _rewrite,
)


_OLD = '''        if bounds[0] < 0:
            return -1
        text = parameters[bounds[0]:bounds[1]]'''
_NEW = '''        if bounds[0] < 0 or bounds[0] >= bounds[1]:
            return -1
        text = parameters[bounds[0]:bounds[1]]'''


def rewrite_generated_function_parameter_kinds(path: Path) -> Path:
    _rewrite(path)
    source = path.read_text(encoding="utf-8")
    if _OLD not in source:
        raise ValueError("generated parameter raw-index helper is unexpected")
    path.write_text(source.replace(_OLD, _NEW, 1), encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function_parameter_kinds"]
