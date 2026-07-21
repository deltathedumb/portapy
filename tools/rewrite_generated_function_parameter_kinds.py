"""Add ``/`` and bare ``*`` parameter-kind semantics to generated functions."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_function_default_capture import _captured_invoke_function
from tools.rewrite_generated_parser import _replace_function


_POSITIONAL_BINDING = r'''    positional = 0
    index = 0
    error_message = ""
    while index < argument_count:
        name = _call_argument_names[argument_start + index]
        target = -1
        if name == "":
            target = positional
            positional += 1
            if target >= expected:
                error_message = "too many positional arguments"
        else:
            target = _parameter_index(parameters, name)
            if target < 0:
                error_message = "unexpected keyword argument"'''

_KIND_BINDING = r'''    positional = 0
    index = 0
    error_message = ""
    while index < argument_count:
        name = _call_argument_names[argument_start + index]
        target = -1
        if name == "":
            target = _next_positional_parameter(parameters, positional)
            if target < 0:
                error_message = "too many positional arguments"
            else:
                positional = target + 1
        else:
            target = _parameter_index(parameters, name)
            if target < 0:
                error_message = "unexpected keyword argument"
            elif _parameter_kind(parameters, target) == _PARAMETER_POSITIONAL_ONLY:
                error_message = "positional-only argument passed as keyword"'''


def _parameter_item_helpers() -> str:
    return r'''_PARAMETER_POSITIONAL_OR_KEYWORD = 0
_PARAMETER_POSITIONAL_ONLY = 1
_PARAMETER_KEYWORD_ONLY = 2


def _raw_parameter_item_bounds(parameters: str, wanted: int) -> list[int]:
    quote = ""
    escaped = False
    depth = 0
    start = 0
    current = 0
    position = 0
    while position <= len(parameters):
        at_end = position == len(parameters)
        char = "" if at_end else parameters[position]
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
                depth += 1
            elif char == ")":
                if depth > 0:
                    depth -= 1
            elif char == "," and depth == 0:
                split = True
        if split:
            if current == wanted:
                bounds = _trim(parameters, start, position)
                return [bounds[0], bounds[1]]
            current += 1
            start = position + 1
        position += 1
    return [-1, -1]


def _raw_parameter_text(parameters: str, raw_index: int) -> str:
    bounds = _raw_parameter_item_bounds(parameters, raw_index)
    if bounds[0] < 0:
        return ""
    return parameters[bounds[0]:bounds[1]]


def _parameter_raw_index(parameters: str, wanted: int) -> int:
    raw_index = 0
    parameter_index = 0
    while True:
        bounds = _raw_parameter_item_bounds(parameters, raw_index)
        if bounds[0] < 0:
            return -1
        text = parameters[bounds[0]:bounds[1]]
        if text != "/" and text != "*":
            if parameter_index == wanted:
                return raw_index
            parameter_index += 1
        raw_index += 1


def _parameter_item_bounds(parameters: str, wanted: int) -> list[int]:
    raw_index = _parameter_raw_index(parameters, wanted)
    if raw_index < 0:
        return [-1, -1]
    return _raw_parameter_item_bounds(parameters, raw_index)'''


def _parameter_count() -> str:
    return r'''def _parameter_count(parameters: str) -> int:
    count = 0
    while _parameter_raw_index(parameters, count) >= 0:
        count += 1
    return count'''


def _parameter_at() -> str:
    return r'''def _parameter_at(parameters: str, wanted: int) -> str:
    bounds = _parameter_item_bounds(parameters, wanted)
    if bounds[0] < 0:
        return ""
    equal = _function_find_equal(parameters, bounds[0], bounds[1])
    end = bounds[1] if equal < 0 else equal
    name_bounds = _trim(parameters, bounds[0], end)
    return parameters[name_bounds[0]:name_bounds[1]]'''


def _parameter_default_bounds() -> str:
    return r'''def _parameter_default_bounds(parameters: str, wanted: int) -> list[int]:
    bounds = _parameter_item_bounds(parameters, wanted)
    if bounds[0] < 0:
        return [-1, -1, 0]
    equal = _function_find_equal(parameters, bounds[0], bounds[1])
    if equal < 0:
        return [-1, -1, 0]
    value_bounds = _trim(parameters, equal + 1, bounds[1])
    if value_bounds[0] >= value_bounds[1]:
        return [equal + 1, equal + 1, -1]
    return [value_bounds[0], value_bounds[1], 1]'''


def _parameter_index_and_kind() -> str:
    return r'''def _parameter_kind(parameters: str, wanted: int) -> int:
    target_raw = _parameter_raw_index(parameters, wanted)
    if target_raw < 0:
        return _PARAMETER_POSITIONAL_OR_KEYWORD
    raw_index = 0
    slash_raw = -1
    star_raw = -1
    while True:
        bounds = _raw_parameter_item_bounds(parameters, raw_index)
        if bounds[0] < 0:
            break
        text = parameters[bounds[0]:bounds[1]]
        if text == "/":
            slash_raw = raw_index
        elif text == "*":
            star_raw = raw_index
        raw_index += 1
    if slash_raw >= 0 and target_raw < slash_raw:
        return _PARAMETER_POSITIONAL_ONLY
    if star_raw >= 0 and target_raw > star_raw:
        return _PARAMETER_KEYWORD_ONLY
    return _PARAMETER_POSITIONAL_OR_KEYWORD


def _next_positional_parameter(parameters: str, start: int) -> int:
    count = _parameter_count(parameters)
    index = start
    while index < count:
        if _parameter_kind(parameters, index) != _PARAMETER_KEYWORD_ONLY:
            return index
        index += 1
    return -1


def _parameter_index(parameters: str, name: str) -> int:
    index = 0
    count = _parameter_count(parameters)
    while index < count:
        if _parameter_at(parameters, index) == name:
            return index
        index += 1
    return -1'''


def _parse_parameters() -> str:
    return r'''def _parse_parameters(source: str, start: int, end: int) -> list[object]:
    original_start = start
    count = 0
    saw_default = False
    saw_slash = False
    saw_star = False
    keyword_after_star = False
    item_start = start
    quote = ""
    escaped = False
    depth = 0
    position = start
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
                depth += 1
            elif char == ")":
                if depth > 0:
                    depth -= 1
            elif char == "," and depth == 0:
                split = True
        if split:
            item = _trim(source, item_start, position)
            if item[0] >= item[1]:
                if count == 0 and not saw_slash and not saw_star and at_end:
                    return ["", 0, PORTAPY_OK]
                return ["", position, PORTAPY_COMPILE_ERROR]
            text = source[item[0]:item[1]]
            if text == "/":
                if saw_slash or saw_star or count == 0:
                    return ["", item[0], PORTAPY_COMPILE_ERROR]
                saw_slash = True
            elif text == "*":
                if saw_star:
                    return ["", item[0], PORTAPY_COMPILE_ERROR]
                saw_star = True
            elif text[0] == "*":
                return ["", item[0], PORTAPY_COMPILE_ERROR]
            else:
                equal = _function_find_equal(source, item[0], item[1])
                name_end = item[1] if equal < 0 else equal
                name_bounds = _trim(source, item[0], name_end)
                parsed_name = _parse_identifier_bounds(source, name_bounds[1], name_bounds[0])
                if parsed_name[2] != PORTAPY_OK or parsed_name[0] != name_bounds[0] or parsed_name[1] != name_bounds[1]:
                    return ["", name_bounds[0], PORTAPY_COMPILE_ERROR]
                name = source[name_bounds[0]:name_bounds[1]]
                check = 0
                previous = source[original_start:item[0]]
                while check < count:
                    if _parameter_at(previous, check) == name:
                        return ["", name_bounds[0], PORTAPY_COMPILE_ERROR]
                    check += 1
                if equal >= 0:
                    default_bounds = _trim(source, equal + 1, item[1])
                    if default_bounds[0] >= default_bounds[1]:
                        return ["", equal + 1, PORTAPY_COMPILE_ERROR]
                    if not saw_star:
                        saw_default = True
                elif saw_default and not saw_star:
                    return ["", name_bounds[0], PORTAPY_COMPILE_ERROR]
                if saw_star:
                    keyword_after_star = True
                count += 1
            item_start = position + 1
        position += 1
    if quote != "" or depth != 0:
        return ["", end, PORTAPY_COMPILE_ERROR]
    if saw_star and not keyword_after_star:
        return ["", end, PORTAPY_COMPILE_ERROR]
    return [source[original_start:end], count, PORTAPY_OK]'''


def _kind_aware_invoke() -> str:
    source = _captured_invoke_function()
    if _POSITIONAL_BINDING not in source:
        raise ValueError("captured argument binder has an unexpected implementation")
    return source.replace(_POSITIONAL_BINDING, _KIND_BINDING, 1)


def rewrite_generated_function_parameter_kinds(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    source = _replace_function(source, "_parameter_item_bounds", _parameter_item_helpers())
    source = _replace_function(source, "_parameter_count", _parameter_count())
    source = _replace_function(source, "_parameter_at", _parameter_at())
    source = _replace_function(
        source,
        "_parameter_default_bounds",
        _parameter_default_bounds(),
    )
    source = _replace_function(source, "_parameter_index", _parameter_index_and_kind())
    source = _replace_function(source, "_parse_parameters", _parse_parameters())
    source = _replace_function(source, "_invoke_function", _kind_aware_invoke())
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function_parameter_kinds"]
