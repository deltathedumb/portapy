"""Corrected public rewrite entry used by native builds and tests."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import (
    _replace_function,
    rewrite_generated_scalar,
)


def _word_operator() -> str:
    return r'''def _find_word_operator(source: str, start: int, end: int, word: str) -> int:
    quote = ""
    escaped = False
    depth = 0
    position = start
    while position < end:
        char = source[position]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            position += 1
            continue
        if char == "'" or char == '"':
            quote = char
            position += 1
            continue
        if char == "(":
            depth += 1
            position += 1
            continue
        if char == ")":
            if depth > 0:
                depth -= 1
            position += 1
            continue
        if depth == 0:
            if word == "and" and position + 3 <= end and source[position:position + 3] == "and":
                if (position == start or not _identifier_char(source[position - 1])) and (
                    position + 3 == end or not _identifier_char(source[position + 3])
                ):
                    return position
            if word == "or" and position + 2 <= end and source[position:position + 2] == "or":
                if (position == start or not _identifier_char(source[position - 1])) and (
                    position + 2 == end or not _identifier_char(source[position + 2])
                ):
                    return position
        position += 1
    return -1'''


def rewrite_generated_expression(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    source = _replace_function(source, "_find_word_operator", _word_operator())
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_expression", "rewrite_generated_scalar"]
