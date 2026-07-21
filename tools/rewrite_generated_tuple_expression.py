"""Teach generated boolean expressions about native tuple truthiness."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function


def _truthy() -> str:
    return r'''def _truthy(runtime: int, value: int) -> list[int]:
    if not _value_is_valid(runtime, value):
        return [0, PORTAPY_INVALID_HANDLE]
    kind = _value_kind[value]
    if kind == PORTAPY_VALUE_NONE:
        return [0, PORTAPY_OK]
    if kind == PORTAPY_VALUE_BOOL or kind == PORTAPY_VALUE_INT:
        return [1 if _value_i64[value] != 0 else 0, PORTAPY_OK]
    if kind == PORTAPY_VALUE_FLOAT:
        bits = _value_i64[value]
        if bits == 0 or bits == -9223372036854775808:
            return [0, PORTAPY_OK]
        return [1, PORTAPY_OK]
    if kind == PORTAPY_VALUE_STRING or kind == PORTAPY_VALUE_BYTES:
        return [1 if _value_data_size[value] != 0 else 0, PORTAPY_OK]
    if kind == 8:
        return [1 if _scalar_tuple_size_unchecked(value) != 0 else 0, PORTAPY_OK]
    return [1, PORTAPY_OK]'''


def rewrite_generated_tuple_expression(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    marker = "    _scalar_retain_global,\n)"
    if marker not in source:
        raise ValueError("generated expression entry has an unexpected scalar import")
    source = source.replace(
        marker,
        "    _scalar_retain_global,\n    _scalar_tuple_size_unchecked,\n)",
        1,
    )
    source = _replace_function(source, "_truthy", _truthy())
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_tuple_expression"]
