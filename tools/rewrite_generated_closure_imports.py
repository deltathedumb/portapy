"""Ensure generated function entries import closure ownership primitives."""
from __future__ import annotations

from pathlib import Path


_IMPORT = "from .native_api import _value_refs\n"


def rewrite_generated_closure_imports(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    if _IMPORT in source:
        return path
    marker = "from __future__ import annotations\n"
    if marker not in source:
        raise ValueError("generated function entry is missing future annotations import")
    source = source.replace(marker, marker + "\n" + _IMPORT, 1)
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_closure_imports"]
