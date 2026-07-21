"""Add native-safe default and keyword argument binding to generated functions."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function


def _parameter_helpers() -> str:
    return r'''def _function_find_equal(source: str, start: int, end: int) -> int:
    quote = ""
    escaped = False
    depth = 0
    position = start
    while position < end:
        char = source[position]
        if quote != "":
            if escaped:
                escaped = False
            elif ord(char) == 92:
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
        if char == "=" and depth == 0:
            previous = source[position - 1] if position > start else ""
            following = source[position + 1] if position + 1 < end else ""
            if previous != "=" and previous != "!" and previous != "<" and previous != ">" and following != "=":
                return position
        position += 1
    return -1


def _parameter_item_bounds(parameters: str, wanted: int) -> list[int]:
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


def _parameter_count(parameters: str) -> int:
    if parameters == "":
        return 0
    count = 0
    while True:
        bounds = _parameter_item_bounds(parameters, count)
        if bounds[0] < 0:
            return count
        count += 1


def _parameter_at(parameters: str, wanted: int) -> str:
    bounds = _parameter_item_bounds(parameters, wanted)
    if bounds[0] < 0:
        return ""
    equal = _function_find_equal(parameters, bounds[0], bounds[1])
    end = bounds[1] if equal < 0 else equal
    name_bounds = _trim(parameters, bounds[0], end)
    return parameters[name_bounds[0]:name_bounds[1]]


def _parameter_default_bounds(parameters: str, wanted: int) -> list[int]:
    bounds = _parameter_item_bounds(parameters, wanted)
    if bounds[0] < 0:
        return [-1, -1, 0]
    equal = _function_find_equal(parameters, bounds[0], bounds[1])
    if equal < 0:
        return [-1, -1, 0]
    value_bounds = _trim(parameters, equal + 1, bounds[1])
    if value_bounds[0] >= value_bounds[1]:
        return [equal + 1, equal + 1, -1]
    return [value_bounds[0], value_bounds[1], 1]


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
                if count == 0 and at_end:
                    return ["", 0, PORTAPY_OK]
                return ["", position, PORTAPY_COMPILE_ERROR]
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
                saw_default = True
            elif saw_default:
                return ["", name_bounds[0], PORTAPY_COMPILE_ERROR]
            count += 1
            item_start = position + 1
        position += 1
    if quote != "" or depth != 0:
        return ["", end, PORTAPY_COMPILE_ERROR]
    return [source[original_start:end], count, PORTAPY_OK]'''


def _call_helpers() -> str:
    return r'''def _call_keyword_bounds(source: str, start: int, end: int) -> list[int]:
    equal = _function_find_equal(source, start, end)
    if equal < 0:
        return [-1, -1, start, 0, PORTAPY_OK]
    name_bounds = _trim(source, start, equal)
    parsed = _parse_identifier_bounds(source, name_bounds[1], name_bounds[0])
    if parsed[2] != PORTAPY_OK or parsed[0] != name_bounds[0] or parsed[1] != name_bounds[1]:
        return [-1, -1, equal, 0, PORTAPY_COMPILE_ERROR]
    value_bounds = _trim(source, equal + 1, end)
    if value_bounds[0] >= value_bounds[1]:
        return [-1, -1, equal + 1, 0, PORTAPY_COMPILE_ERROR]
    return [name_bounds[0], name_bounds[1], value_bounds[0], 1, PORTAPY_OK]


def _push_call_argument(name: str, value: int) -> None:
    top = _call_argument_top[0]
    if top < len(_call_argument_values):
        _call_argument_values[top] = value
        _call_argument_names[top] = name
    else:
        _call_argument_values.append(value)
        _call_argument_names.append(name)
    _call_argument_top[0] = top + 1


def _release_call_arguments(runtime: int, start: int, count: int) -> None:
    index = 0
    while index < count:
        _scalar_release(runtime, _call_argument_values[start + index])
        index += 1


def _release_bound_defaults(runtime: int, start: int, count: int) -> None:
    index = 0
    while index < count:
        if _call_bound_owned[start + index] != 0:
            _scalar_release(runtime, _call_bound_values[start + index])
        index += 1


def _function_argument_error(
    runtime: int,
    slot: int,
    position: int,
    message: str,
) -> list[int]:
    _fail(
        runtime,
        PORTAPY_TYPE_ERROR,
        "TypeError",
        message,
        _function_definition_line[slot],
        1,
    )
    return [0, position, PORTAPY_TYPE_ERROR]'''


def _parse_call_or_expression() -> str:
    return r'''def _parse_call_or_expression(runtime: int, source: str, start: int, end: int) -> list[int]:
    call = _direct_call_bounds(source, start, end)
    if call[3] == 0:
        return _expr_parse_boolean_expression(runtime, source, start, end)
    function_slot = _find_function_slot(runtime, call[0])
    if function_slot == 0:
        return _expr_parse_boolean_expression(runtime, source, start, end)
    arguments = _argument_spans(source, int(call[1]), int(call[2]))
    if arguments[0] != PORTAPY_OK:
        return [0, arguments[1], arguments[0]]
    argument_start = _call_argument_top[0]
    saw_keyword = False
    index = 2
    while index < len(arguments):
        item_start = arguments[index]
        item_end = arguments[index + 1]
        keyword = _call_keyword_bounds(source, item_start, item_end)
        if keyword[4] != PORTAPY_OK:
            _release_call_arguments(
                runtime,
                argument_start,
                _call_argument_top[0] - argument_start,
            )
            _call_argument_top[0] = argument_start
            return [0, keyword[2], keyword[4]]
        name = ""
        value_start = item_start
        if keyword[3] != 0:
            saw_keyword = True
            name = source[keyword[0]:keyword[1]]
            value_start = keyword[2]
        elif saw_keyword:
            _release_call_arguments(
                runtime,
                argument_start,
                _call_argument_top[0] - argument_start,
            )
            _call_argument_top[0] = argument_start
            return [0, item_start, PORTAPY_COMPILE_ERROR]
        parsed = _parse_call_or_expression(runtime, source, value_start, item_end)
        if parsed[2] != PORTAPY_OK:
            _release_call_arguments(
                runtime,
                argument_start,
                _call_argument_top[0] - argument_start,
            )
            _call_argument_top[0] = argument_start
            return parsed
        _push_call_argument(name, parsed[0])
        index += 2
    argument_count = _call_argument_top[0] - argument_start
    result = _invoke_function(runtime, function_slot, argument_start, argument_count, start)
    _call_argument_top[0] = argument_start
    return result'''


def _invoke_function() -> str:
    return r'''def _invoke_function(
    runtime: int,
    slot: int,
    argument_start: int,
    argument_count: int,
    position: int,
) -> list[int]:
    parameters = _function_parameters[slot]
    expected = _parameter_count(parameters)
    bound_start = _call_bound_top[0]
    index = 0
    while index < expected:
        top = _call_bound_top[0]
        if top < len(_call_bound_values):
            _call_bound_values[top] = 0
            _call_bound_set[top] = 0
            _call_bound_owned[top] = 0
        else:
            _call_bound_values.append(0)
            _call_bound_set.append(0)
            _call_bound_owned.append(0)
        _call_bound_top[0] = top + 1
        index += 1

    positional = 0
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
                error_message = "unexpected keyword argument"
        if error_message == "" and _call_bound_set[bound_start + target] != 0:
            error_message = "multiple values for function argument"
        if error_message != "":
            _release_call_arguments(runtime, argument_start, argument_count)
            _release_bound_defaults(runtime, bound_start, expected)
            _call_bound_top[0] = bound_start
            return _function_argument_error(runtime, slot, position, error_message)
        _call_bound_values[bound_start + target] = _call_argument_values[argument_start + index]
        _call_bound_set[bound_start + target] = 1
        index += 1

    index = 0
    while index < expected:
        if _call_bound_set[bound_start + index] == 0:
            default_bounds = _parameter_default_bounds(parameters, index)
            if default_bounds[2] < 0:
                _release_call_arguments(runtime, argument_start, argument_count)
                _release_bound_defaults(runtime, bound_start, expected)
                _call_bound_top[0] = bound_start
                return _function_argument_error(
                    runtime,
                    slot,
                    position,
                    "invalid default argument",
                )
            if default_bounds[2] == 0:
                _release_call_arguments(runtime, argument_start, argument_count)
                _release_bound_defaults(runtime, bound_start, expected)
                _call_bound_top[0] = bound_start
                return _function_argument_error(
                    runtime,
                    slot,
                    position,
                    "missing required function argument",
                )
            parsed_default = _expr_parse_boolean_expression(
                runtime,
                parameters,
                default_bounds[0],
                default_bounds[1],
            )
            if parsed_default[2] != PORTAPY_OK:
                _release_call_arguments(runtime, argument_start, argument_count)
                _release_bound_defaults(runtime, bound_start, expected)
                _call_bound_top[0] = bound_start
                _expr_record_expression_failure(
                    runtime,
                    parsed_default[2],
                    parsed_default[1],
                )
                return [0, position, parsed_default[2]]
            _call_bound_values[bound_start + index] = parsed_default[0]
            _call_bound_set[bound_start + index] = 1
            _call_bound_owned[bound_start + index] = 1
        index += 1

    _ensure_runtime_state(runtime)
    if _call_depth[runtime] >= _MAX_CALL_DEPTH:
        _release_call_arguments(runtime, argument_start, argument_count)
        _release_bound_defaults(runtime, bound_start, expected)
        _call_bound_top[0] = bound_start
        _fail(
            runtime,
            PORTAPY_RUNTIME_ERROR,
            "RecursionError",
            "maximum PortaPy call depth exceeded",
            _function_definition_line[slot],
            1,
        )
        return [0, position, PORTAPY_RUNTIME_ERROR]

    names = _collect_local_names(_function_body[slot], parameters)
    saved_names: list[str] = []
    saved_existed: list[int] = []
    saved_values: list[int] = []
    index = 0
    while index < len(names):
        _save_binding(runtime, names[index], saved_names, saved_existed, saved_values)
        index += 1

    index = 0
    while index < expected:
        parameter = _parameter_at(parameters, index)
        _bind_global(runtime, parameter, _call_bound_values[bound_start + index])
        index += 1

    _call_depth[runtime] += 1
    executed = _execute_function_body(runtime, slot)
    _call_depth[runtime] -= 1
    _restore_bindings(runtime, saved_names, saved_existed, saved_values)
    _call_bound_top[0] = bound_start
    if executed[1] != PORTAPY_OK:
        return [0, position, executed[1]]
    return [executed[0], position, PORTAPY_OK]'''


def rewrite_generated_function_arguments(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    marker = "_call_argument_top: list[int] = [1]\n"
    if marker not in source:
        raise ValueError("generated function entry is missing argument stack top")
    source = source.replace(
        marker,
        marker
        + '_call_argument_names: list[str] = [""]\n'
        + "_call_bound_values: list[int] = [0]\n"
        + "_call_bound_set: list[int] = [0]\n"
        + "_call_bound_owned: list[int] = [0]\n"
        + "_call_bound_top: list[int] = [1]\n",
        1,
    )
    source = _replace_function(source, "_parameter_count", _parameter_helpers())
    source = _replace_function(source, "_parse_parameters", _parse_parameters())
    source = _replace_function(source, "_parse_call_or_expression", _call_helpers() + "\n\n" + _parse_call_or_expression())
    source = _replace_function(source, "_invoke_function", _invoke_function())
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function_arguments"]
