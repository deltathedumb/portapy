"""Finalize generated default/keyword binding without duplicate helpers."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_function_arguments import (
    rewrite_generated_function_arguments as _rewrite,
)


def _function_end(source: str, start: int, marker_size: int) -> int:
    next_function = source.find("\ndef ", start + marker_size)
    return len(source) if next_function < 0 else next_function + 1


def _remove_first_function(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        raise ValueError(f"generated source is missing {name}")
    end = _function_end(source, start, len(marker))
    return source[:start] + source[end:]


def _remove_second_function(source: str, name: str) -> str:
    marker = f"def {name}("
    first = source.find(marker)
    if first < 0:
        raise ValueError(f"generated source is missing {name}")
    second = source.find(marker, first + len(marker))
    if second < 0:
        raise ValueError(f"generated source does not contain legacy duplicate {name}")
    end = _function_end(source, second, len(marker))
    return source[:second] + source[end:]


def rewrite_generated_function_arguments(path: Path) -> Path:
    _rewrite(path)
    source = path.read_text(encoding="utf-8")
    source = _remove_second_function(source, "_parameter_at")
    source = _remove_first_function(source, "_push_call_argument")
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function_arguments"]
