"""Native-safe rewrites used by generated PortaPy parser entries."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_dict_safe import rewrite_generated_dict
from tools.rewrite_generated_dict_expression import rewrite_generated_dict_expression
from tools.rewrite_generated_parser import (
    _replace_function,
    rewrite_generated_scalar as _rewrite_generated_scalar,
)
from tools.rewrite_generated_tuple_native_utf8 import rewrite_generated_tuple
from tools.rewrite_generated_tuple_expression import rewrite_generated_tuple_expression


def rewrite_generated_scalar(path: Path) -> Path:
    """Apply scalar rewrites and native tuple/dictionary semantics."""
    _rewrite_generated_scalar(path)
    source = path.read_text(encoding="utf-8")
    source = source.replace("if not operator[0]:", 'if operator[0] == "":')
    source = source.replace("if assignment[0]:", 'if assignment[0] != "":')
    path.write_text(source, encoding="utf-8")
    rewrite_generated_tuple(path)
    rewrite_generated_dict(path)
    return path


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


def _explicit_augmented_operator(indent: str) -> str:
    return (
        f'{indent}operator = ""\n'
        f'{indent}if assignment[0] == "+=":\n'
        f'{indent}    operator = "+"\n'
        f'{indent}elif assignment[0] == "-=":\n'
        f'{indent}    operator = "-"\n'
        f'{indent}elif assignment[0] == "*=":\n'
        f'{indent}    operator = "*"\n'
        f'{indent}elif assignment[0] == "//=":\n'
        f'{indent}    operator = "//"\n'
        f'{indent}elif assignment[0] == "%=":\n'
        f'{indent}    operator = "%"\n'
        f'{indent}elif assignment[0] == "&=":\n'
        f'{indent}    operator = "&"\n'
        f'{indent}elif assignment[0] == "^=":\n'
        f'{indent}    operator = "^"\n'
        f'{indent}elif assignment[0] == "|=":\n'
        f'{indent}    operator = "|"\n'
    )


def _rewrite_augmented_dispatch(source: str, *, indent: str) -> str:
    marker = f'{indent}operator = str(assignment[0])[:-1]\n'
    if marker not in source:
        raise ValueError("generated parser is missing augmented operator conversion")
    return source.replace(marker, _explicit_augmented_operator(indent), 1)


def rewrite_generated_expression(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    source = _replace_function(source, "_find_word_operator", _word_operator())
    source = source.replace("if assignment[0]:", 'if assignment[0] != "":')
    source = _rewrite_augmented_dispatch(source, indent="            ")
    path.write_text(source, encoding="utf-8")
    rewrite_generated_tuple_expression(path)
    rewrite_generated_dict_expression(path)
    return path


def rewrite_generated_control(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    source = _rewrite_augmented_dispatch(source, indent="        ")
    path.write_text(source, encoding="utf-8")
    return path


__all__ = [
    "rewrite_generated_control",
    "rewrite_generated_expression",
    "rewrite_generated_scalar",
]
