"""Repair dependency aliases introduced by the lexical-closure rewrite."""
from __future__ import annotations

from pathlib import Path


_OLD = "    assignment = _find_assignment(statement, len(statement))\n"
_NEW = "    assignment = _scalar_find_assignment(statement, len(statement))\n"


def rewrite_generated_closure_aliases(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    count = source.count(_OLD)
    if count != 1:
        raise ValueError(
            "generated closure statement executor has an unexpected assignment alias: "
            f"found {count} matches"
        )
    path.write_text(source.replace(_OLD, _NEW, 1), encoding="utf-8")
    return path


__all__ = ["rewrite_generated_closure_aliases"]
