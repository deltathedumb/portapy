"""Apply asmpython-safe rewrites to the generated native function entry."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function


_REPLACEMENTS = {
    "str(header[0])": "header[0]",
    "str(header[1])": "header[1]",
    "str(call[0])": "call[0]",
    "str(assignment[0])": "assignment[0]",
}


def _parameter_at() -> str:
    return '''def _parameter_at(parameters: str, wanted: int) -> str:
    start = 0
    current = 0
    index = 0
    while index <= len(parameters):
        if index == len(parameters) or parameters[index] == ",":
            if current == wanted:
                left = start
                right = index
                while left < right and parameters[left].isspace():
                    left += 1
                while right > left and parameters[right - 1].isspace():
                    right -= 1
                return parameters[left:right]
            current += 1
            start = index + 1
        index += 1
    return ""'''


def _parse_parameters() -> str:
    return '''def _parse_parameters(source: str, start: int, end: int) -> list[object]:
    original_start = start
    count = 0
    position = start
    while True:
        position = _skip_space(source, end, position)
        if position >= end:
            if count == 0:
                return ["", count, PORTAPY_OK]
            return [source[original_start:end], count, PORTAPY_OK]
        bounds = _parse_identifier_bounds(source, end, position)
        if bounds[2] != PORTAPY_OK:
            return ["", bounds[1], PORTAPY_COMPILE_ERROR]
        name = source[bounds[0]:bounds[1]]
        previous = source[original_start:bounds[0]]
        check = 0
        while check < count:
            if _parameter_at(previous, check) == name:
                return ["", bounds[0], PORTAPY_COMPILE_ERROR]
            check += 1
        count += 1
        position = _skip_space(source, end, bounds[1])
        if position >= end:
            return [source[original_start:end], count, PORTAPY_OK]
        if source[position] != ",":
            return ["", position, PORTAPY_COMPILE_ERROR]
        position += 1
        if _skip_space(source, end, position) >= end:
            return ["", position, PORTAPY_COMPILE_ERROR]'''


def rewrite_generated_function(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    for old, new in _REPLACEMENTS.items():
        if old not in source:
            raise ValueError(f"generated function entry is missing conversion: {old}")
        source = source.replace(old, new)
    source = _replace_function(source, "_parameter_at", _parameter_at())
    source = _replace_function(source, "_parse_parameters", _parse_parameters())
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function"]
