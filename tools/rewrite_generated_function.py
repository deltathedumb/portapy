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


def _argument_spans() -> str:
    return '''def _argument_spans(source: str, start: int, end: int) -> list[int]:
    result: list[int] = [PORTAPY_OK, end]
    bounds = _trim(source, start, end)
    start = bounds[0]
    end = bounds[1]
    if start >= end:
        return result
    quote = ""
    escaped = False
    depth = 0
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
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
            elif char == "'" or char == '"':
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                if depth <= 0:
                    return [PORTAPY_COMPILE_ERROR, position]
                depth -= 1
            elif char == "," and depth == 0:
                split = True
        if split:
            item = _trim(source, item_start, position)
            if item[0] >= item[1]:
                return [PORTAPY_COMPILE_ERROR, position]
            result.append(item[0])
            result.append(item[1])
            item_start = position + 1
        position += 1
    if quote != "" or depth != 0:
        return [PORTAPY_COMPILE_ERROR, end]
    return result'''


def _parse_call_or_expression() -> str:
    return '''def _parse_call_or_expression(runtime: int, source: str, start: int, end: int) -> list[int]:
    call = _direct_call_bounds(source, start, end)
    if call[3] == 0:
        return _expr_parse_boolean_expression(runtime, source, start, end)
    function_slot = _find_function_slot(runtime, call[0])
    if function_slot == 0:
        return _expr_parse_boolean_expression(runtime, source, start, end)
    arguments = _argument_spans(source, int(call[1]), int(call[2]))
    if arguments[0] != PORTAPY_OK:
        return [0, arguments[1], arguments[0]]
    argument_start = len(_call_argument_values)
    index = 2
    while index < len(arguments):
        parsed = _parse_call_or_expression(runtime, source, arguments[index], arguments[index + 1])
        if parsed[2] != PORTAPY_OK:
            release = argument_start
            while release < len(_call_argument_values):
                _scalar_release(runtime, _call_argument_values[release])
                release += 1
            return parsed
        _call_argument_values.append(parsed[0])
        index += 2
    argument_count = len(_call_argument_values) - argument_start
    return _invoke_function(runtime, function_slot, argument_start, argument_count, start)'''


def _invoke_function() -> str:
    return '''def _invoke_function(
    runtime: int,
    slot: int,
    argument_start: int,
    argument_count: int,
    position: int,
) -> list[int]:
    expected = _parameter_count(_function_parameters[slot])
    if argument_count != expected:
        index = 0
        while index < argument_count:
            _scalar_release(runtime, _call_argument_values[argument_start + index])
            index += 1
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "function argument count mismatch", _function_definition_line[slot], 1)
        return [0, position, PORTAPY_TYPE_ERROR]
    _ensure_runtime_state(runtime)
    if _call_depth[runtime] >= _MAX_CALL_DEPTH:
        index = 0
        while index < argument_count:
            _scalar_release(runtime, _call_argument_values[argument_start + index])
            index += 1
        _fail(runtime, PORTAPY_RUNTIME_ERROR, "RecursionError", "maximum PortaPy call depth exceeded", _function_definition_line[slot], 1)
        return [0, position, PORTAPY_RUNTIME_ERROR]

    names = _collect_local_names(_function_body[slot], _function_parameters[slot])
    saved_names: list[str] = []
    saved_existed: list[int] = []
    saved_values: list[int] = []
    index = 0
    while index < len(names):
        _save_binding(runtime, names[index], saved_names, saved_existed, saved_values)
        index += 1

    index = 0
    while index < expected:
        parameter = _parameter_at(_function_parameters[slot], index)
        _bind_global(runtime, parameter, _call_argument_values[argument_start + index])
        index += 1

    _call_depth[runtime] += 1
    executed = _execute_function_body(runtime, slot)
    _call_depth[runtime] -= 1
    _restore_bindings(runtime, saved_names, saved_existed, saved_values)
    if executed[1] != PORTAPY_OK:
        return [0, position, executed[1]]
    return [executed[0], position, PORTAPY_OK]'''


def rewrite_generated_function(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    for old, new in _REPLACEMENTS.items():
        if old not in source:
            raise ValueError(f"generated function entry is missing conversion: {old}")
        source = source.replace(old, new)
    source = source.replace(
        "_call_depth: list[int] = [0]\n",
        "_call_depth: list[int] = [0]\n_call_argument_values: list[int] = [0]\n",
        1,
    )
    source = _replace_function(source, "_parameter_at", _parameter_at())
    source = _replace_function(source, "_parse_parameters", _parse_parameters())
    source = _replace_function(source, "_argument_spans", _argument_spans())
    source = _replace_function(source, "_parse_call_or_expression", _parse_call_or_expression())
    source = _replace_function(source, "_invoke_function", _invoke_function())
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function"]
