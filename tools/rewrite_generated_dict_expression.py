"""Teach generated boolean expressions about native dictionaries."""
from __future__ import annotations

from pathlib import Path


_OLD_TRUTHINESS = r'''    if kind == 8:
        return [1 if _scalar_tuple_size_unchecked(value) != 0 else 0, PORTAPY_OK]
    return [1, PORTAPY_OK]'''

_NEW_TRUTHINESS = r'''    if kind == 8:
        return [1 if _scalar_tuple_size_unchecked(value) != 0 else 0, PORTAPY_OK]
    if kind == 9:
        return [1 if _scalar_dict_size_unchecked(value) != 0 else 0, PORTAPY_OK]
    return [1, PORTAPY_OK]'''


def rewrite_generated_dict_expression(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    marker = "    _scalar_tuple_size_unchecked,\n"
    if marker not in source:
        raise ValueError("generated expression entry is missing tuple helper import")
    source = source.replace(
        marker,
        marker + "    _scalar_dict_size_unchecked,\n",
        1,
    )
    if _OLD_TRUTHINESS not in source:
        raise ValueError("generated expression truthiness has an unexpected implementation")
    source = source.replace(_OLD_TRUTHINESS, _NEW_TRUTHINESS, 1)
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_dict_expression"]
