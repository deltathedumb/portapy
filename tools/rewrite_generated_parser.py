"""Rewrite generated parser helpers into asmpython-safe explicit branches.

The canonical parser sources stay compact and Pythonic. This transform only
removes two lowering-sensitive patterns from ephemeral generated modules:
iteration over operator tuples and dynamic word-operator matching.
"""
from __future__ import annotations

from pathlib import Path


def _replace_function(source: str, name: str, replacement: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        raise ValueError(f"generated parser source is missing {name}")
    if start > 0 and source[start - 1] != "\n":
        raise ValueError(f"generated parser function {name} is not top-level")
    next_function = source.find("\ndef ", start + len(marker))
    end = len(source) if next_function < 0 else next_function + 1
    return source[:start] + replacement.rstrip() + "\n\n" + source[end:]


def _chain(name: str, lower: str, selection: str) -> str:
    return f'''def {name}(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    left = {lower}(runtime, source, source_size, position)
    if left[2] != PORTAPY_OK:
        return left
    while True:
        operator_at = _skip_space(source, source_size, left[1])
        selected = ""
        width = 0
{selection}
        if selected == "":
            return left
        right = {lower}(runtime, source, source_size, operator_at + width)
        if right[2] != PORTAPY_OK:
            _scalar_release(runtime, left[0])
            return right
        result = _scalar_binary(runtime, left[0], right[0], selected, operator_at)
        result[1] = right[1]
        if result[2] != PORTAPY_OK:
            return result
        left = result'''


def _comparison_operator() -> str:
    return '''def _scalar_comparison_operator(source: str, source_size: int, position: int) -> list[object]:
    position = _skip_space(source, source_size, position)
    if position + 1 < source_size and source[position:position + 2] == "==":
        return ["==", position + 2]
    if position + 1 < source_size and source[position:position + 2] == "!=":
        return ["!=", position + 2]
    if position + 1 < source_size and source[position:position + 2] == "<=":
        return ["<=", position + 2]
    if position + 1 < source_size and source[position:position + 2] == ">=":
        return [">=", position + 2]
    if _scalar_keyword_at(source, source_size, position, "is"):
        after = _skip_space(source, source_size, position + 2)
        if _scalar_keyword_at(source, source_size, after, "not"):
            return ["is not", after + 3]
        return ["is", position + 2]
    if position < source_size and source[position] == "<":
        return ["<", position + 1]
    if position < source_size and source[position] == ">":
        return [">", position + 1]
    return ["", position]'''


def rewrite_generated_scalar(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    source = _replace_function(
        source,
        "_scalar_parse_multiply",
        _chain(
            "_scalar_parse_multiply",
            "_scalar_parse_unary",
            '''        if operator_at + 1 < source_size and source[operator_at:operator_at + 2] == "//":
            selected = "//"
            width = 2
        elif operator_at < source_size and source[operator_at] == "*":
            selected = "*"
            width = 1
        elif operator_at < source_size and source[operator_at] == "%":
            selected = "%"
            width = 1
        elif operator_at < source_size and source[operator_at] == "/":
            selected = "/"
            width = 1''',
        ),
    )
    source = _replace_function(
        source,
        "_scalar_parse_add",
        _chain(
            "_scalar_parse_add",
            "_scalar_parse_multiply",
            '''        if operator_at < source_size and source[operator_at] == "+":
            selected = "+"
            width = 1
        elif operator_at < source_size and source[operator_at] == "-":
            selected = "-"
            width = 1''',
        ),
    )
    source = _replace_function(
        source,
        "_scalar_parse_shift",
        _chain(
            "_scalar_parse_shift",
            "_scalar_parse_add",
            '''        if operator_at + 1 < source_size and source[operator_at:operator_at + 2] == "<<":
            selected = "<<"
            width = 2
        elif operator_at + 1 < source_size and source[operator_at:operator_at + 2] == ">>":
            selected = ">>"
            width = 2''',
        ),
    )
    source = _replace_function(
        source,
        "_scalar_parse_bitand",
        _chain(
            "_scalar_parse_bitand",
            "_scalar_parse_shift",
            '''        if operator_at < source_size and source[operator_at] == "&":
            selected = "&"
            width = 1''',
        ),
    )
    source = _replace_function(
        source,
        "_scalar_parse_bitxor",
        _chain(
            "_scalar_parse_bitxor",
            "_scalar_parse_bitand",
            '''        if operator_at < source_size and source[operator_at] == "^":
            selected = "^"
            width = 1''',
        ),
    )
    source = _replace_function(
        source,
        "_scalar_parse_bitor",
        _chain(
            "_scalar_parse_bitor",
            "_scalar_parse_bitxor",
            '''        if operator_at < source_size and source[operator_at] == "|":
            selected = "|"
            width = 1''',
        ),
    )
    source = _replace_function(source, "_scalar_comparison_operator", _comparison_operator())
    path.write_text(source, encoding="utf-8")
    return path


def _word_operator() -> str:
    return '''def _find_word_operator(source: str, start: int, end: int, word: str) -> int:
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
