"""Finalize generated positional variadics and validate helper uniqueness."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_function_varargs import (
    rewrite_generated_function_varargs as _rewrite,
)


def _require_single_function(source: str, name: str) -> None:
    marker = f"def {name}("
    count = source.count(marker)
    if count != 1:
        raise ValueError(
            f"generated source must contain exactly one {name}; found {count}"
        )


def rewrite_generated_function_varargs(path: Path) -> Path:
    _rewrite(path)
    source = path.read_text(encoding="utf-8")
    for name in (
        "_parameter_kind",
        "_var_positional_index",
        "_next_regular_positional_parameter",
        "_next_positional_parameter",
        "_parameter_index",
        "_build_varargs_tuple",
    ):
        _require_single_function(source, name)
    return path


__all__ = ["rewrite_generated_function_varargs"]
