"""Finalize generated dictionary semantics for asmpython lowering."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_dict import rewrite_generated_dict as _rewrite


_ANNOTATED_ITEM = "        item: list[int]\n"
_INITIALIZED_ITEM = "        item = [0, 0, PORTAPY_OK]\n"


def rewrite_generated_dict(path: Path) -> Path:
    _rewrite(path)
    source = path.read_text(encoding="utf-8")
    if _ANNOTATED_ITEM not in source:
        raise ValueError("generated dictionary parser is missing its item temporary")
    path.write_text(
        source.replace(_ANNOTATED_ITEM, _INITIALIZED_ITEM, 1),
        encoding="utf-8",
    )
    return path


__all__ = ["rewrite_generated_dict"]
