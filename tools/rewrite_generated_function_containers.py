"""Make generated function call parsing container-literal aware."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function


def _argument_spans() -> str:
    return r'''def _argument_spans(source: str, start: int, end: int) -> list[int]:
    result: list[int] = [PORTAPY_OK, end]
    bounds = _trim(source, start, end)
    start = bounds[0]
    end = bounds[1]
    if start >= end:
        return result
    quote = ""
    escaped = False
    round_depth = 0
    square_depth = 0
    brace_depth = 0
    position = start
    item_start = start
    while position <= end:
        at_end = position == end
        char = "" if at_end else source[position]
        split = at_end
        if not at_end:
            if quote != "":
                if escaped:
                    escaped = False
                elif ord(char) == 92:
                    escaped = True
                elif char == quote:
                    quote = ""
            elif char == "'" or char == '"':
                quote = char
            elif char == "(":
                round_depth += 1
            elif char == ")":
                if round_depth <= 0:
                    return [PORTAPY_COMPILE_ERROR, position]
                round_depth -= 1
            elif char == "[":
                square_depth += 1
            elif char == "]":
                if square_depth <= 0:
                    return [PORTAPY_COMPILE_ERROR, position]
                square_depth -= 1
            elif char == "{":
                brace_depth += 1
            elif char == "}":
                if brace_depth <= 0:
                    return [PORTAPY_COMPILE_ERROR, position]
                brace_depth -= 1
            elif (
                char == ","
                and round_depth == 0
                and square_depth == 0
                and brace_depth == 0
            ):
                split = True
        if split:
            item = _trim(source, item_start, position)
            if item[0] >= item[1]:
                return [PORTAPY_COMPILE_ERROR, position]
            result.append(item[0])
            result.append(item[1])
            item_start = position + 1
        position += 1
    if quote != "" or round_depth != 0 or square_depth != 0 or brace_depth != 0:
        return [PORTAPY_COMPILE_ERROR, end]
    return result'''


def rewrite_generated_function_containers(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    source = _replace_function(source, "_argument_spans", _argument_spans())
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function_containers"]
