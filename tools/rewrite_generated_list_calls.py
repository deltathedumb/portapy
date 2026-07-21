"""Make generated direct-call argument splitting bracket-aware."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function


def _argument_spans() -> str:
    return r'''def _argument_spans(source: str, start: int, end: int) -> list[int]:
    result: list[int] = [PORTAPY_OK, end]
    quote = ""
    escaped = False
    parentheses = 0
    brackets = 0
    item_start = start
    position = start
    saw_item = False
    while position <= end:
        at_end = position == end
        char = "" if at_end else source[position]
        split = at_end
        if not at_end:
            if quote != "":
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
            elif char == "'" or char == '"':
                quote = char
            elif char == "(":
                parentheses += 1
            elif char == ")":
                if parentheses <= 0:
                    return [PORTAPY_COMPILE_ERROR, position]
                parentheses -= 1
            elif char == "[":
                brackets += 1
            elif char == "]":
                if brackets <= 0:
                    return [PORTAPY_COMPILE_ERROR, position]
                brackets -= 1
            elif char == "," and parentheses == 0 and brackets == 0:
                split = True
        if split:
            left = item_start
            right = position
            while left < right and source[left].isspace():
                left += 1
            while right > left and source[right - 1].isspace():
                right -= 1
            if left < right:
                result.append(left)
                result.append(right)
                saw_item = True
            elif not at_end or (saw_item and item_start < end):
                if at_end and position > start and source[position - 1] == ",":
                    return result
                return [PORTAPY_COMPILE_ERROR, position]
            item_start = position + 1
        position += 1
    if quote != "" or parentheses != 0 or brackets != 0:
        return [PORTAPY_COMPILE_ERROR, end]
    return result'''


def rewrite_generated_list_calls(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    source = _replace_function(source, "_argument_spans", _argument_spans())
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_list_calls"]
