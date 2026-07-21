"""Add native ``*args`` parsing and tuple packing to generated functions."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_function_parameter_kinds import _kind_aware_invoke
from tools.rewrite_generated_parser import _replace_function


_KIND_BINDING_BLOCK = r'''    positional = 0
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
                error_message = "positional-only argument passed as keyword"
        if error_message == "" and _call_bound_set[bound_start + target] != 0:
            error_message = "multiple values for function argument"
        if error_message != "":
            _release_call_arguments(runtime, argument_start, argument_count)
            _release_bound_defaults(runtime, bound_start, expected)
            _call_bound_top[0] = bound_start
            return _function_argument_error(runtime, slot, position, error_message)
        _call_bound_values[bound_start + target] = _call_argument_values[argument_start + index]
        _call_bound_set[bound_start + target] = 1
        index += 1'''

_VARARGS_BINDING_BLOCK = r'''    positional = 0
    varargs_index = _var_positional_index(parameters)
    vararg_positions: list[int] = []
    index = 0
    error_message = ""
    while index < argument_count:
        name = _call_argument_names[argument_start + index]
        target = -1
        if name == "":
            target = _next_regular_positional_parameter(parameters, positional)
            if target < 0:
                if varargs_index >= 0:
                    vararg_positions.append(index)
                else:
                    error_message = "too many positional arguments"
            else:
                positional = target + 1
        else:
            target = _parameter_index(parameters, name)
            if target < 0 or (
                target >= 0
                and _parameter_kind(parameters, target) == _PARAMETER_VAR_POSITIONAL
            ):
                error_message = "unexpected keyword argument"
            elif _parameter_kind(parameters, target) == _PARAMETER_POSITIONAL_ONLY:
                error_message = "positional-only argument passed as keyword"
        if target >= 0:
            if error_message == "" and _call_bound_set[bound_start + target] != 0:
                error_message = "multiple values for function argument"
            if error_message == "":
                _call_bound_values[bound_start + target] = _call_argument_values[argument_start + index]
                _call_bound_set[bound_start + target] = 1
        if error_message != "":
            _release_call_arguments(runtime, argument_start, argument_count)
            _release_bound_defaults(runtime, bound_start, expected)
            _call_bound_top[0] = bound_start
            return _function_argument_error(runtime, slot, position, error_message)
        index += 1'''

_DEFAULT_CONDITION = "        if _call_bound_set[bound_start + index] == 0:\n"
_VARARGS_DEFAULT_CONDITION = (
    "        if (\n"
    "            _call_bound_set[bound_start + index] == 0\n"
    "            and _parameter_kind(parameters, index) != _PARAMETER_VAR_POSITIONAL\n"
    "        ):\n"
)

_RECURSION_END = r'''        return [0, position, PORTAPY_RUNTIME_ERROR]

    names = _collect_local_names(_function_body[slot], parameters)'''

_VARARGS_PACK_INSERTION = r'''        return [0, position, PORTAPY_RUNTIME_ERROR]

    if varargs_index >= 0:
        varargs_value = _build_varargs_tuple(
            runtime,
            argument_start,
            vararg_positions,
        )
        if varargs_value == 0:
            _release_call_arguments(runtime, argument_start, argument_count)
            _release_bound_defaults(runtime, bound_start, expected)
            _call_bound_top[0] = bound_start
            return [0, position, _last_status_value()]
        _call_bound_values[bound_start + varargs_index] = varargs_value
        _call_bound_set[bound_start + varargs_index] = 1
        _call_bound_owned[bound_start + varargs_index] = 1

    names = _collect_local_names(_function_body[slot], parameters)'''


def _parameter_at() -> str:
    return r'''def _parameter_at(parameters: str, wanted: int) -> str:
    bounds = _parameter_item_bounds(parameters, wanted)
    if bounds[0] < 0:
        return ""
    equal = _function_find_equal(parameters, bounds[0], bounds[1])
    end = bounds[1] if equal < 0 else equal
    start = bounds[0]
    while start < end and parameters[start] == "*":
        start += 1
    name_bounds = _trim(parameters, start, end)
    return parameters[name_bounds[0]:name_bounds[1]]'''


def _parameter_kind() -> str:
    return r'''_PARAMETER_VAR_POSITIONAL = 3


def _parameter_kind(parameters: str, wanted: int) -> int:
    target_raw = _parameter_raw_index(parameters, wanted)
    if target_raw < 0:
        return _PARAMETER_POSITIONAL_OR_KEYWORD
    target_bounds = _raw_parameter_item_bounds(parameters, target_raw)
    target_text = parameters[target_bounds[0]:target_bounds[1]]
    if len(target_text) > 1 and target_text[0] == "*" and target_text[1] != "*":
        return _PARAMETER_VAR_POSITIONAL
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
        elif text == "*" or (
            len(text) > 1 and text[0] == "*" and text[1] != "*"
        ):
            star_raw = raw_index
        raw_index += 1
    if slash_raw >= 0 and target_raw < slash_raw:
        return _PARAMETER_POSITIONAL_ONLY
    if star_raw >= 0 and target_raw > star_raw:
        return _PARAMETER_KEYWORD_ONLY
    return _PARAMETER_POSITIONAL_OR_KEYWORD'''


def _positional_helpers_and_tuple_builder() -> str:
    return r'''def _var_positional_index(parameters: str) -> int:
    count = _parameter_count(parameters)
    index = 0
    while index < count:
        if _parameter_kind(parameters, index) == _PARAMETER_VAR_POSITIONAL:
            return index
        index += 1
    return -1


def _next_regular_positional_parameter(parameters: str, start: int) -> int:
    count = _parameter_count(parameters)
    index = start
    while index < count:
        kind = _parameter_kind(parameters, index)
        if kind == _PARAMETER_VAR_POSITIONAL:
            index += 1
            continue
        if kind == _PARAMETER_KEYWORD_ONLY:
            return -1
        return index
    return -1


def _next_positional_parameter(parameters: str, start: int) -> int:
    return _next_regular_positional_parameter(parameters, start)


def _build_varargs_tuple(
    runtime: int,
    argument_start: int,
    positions: list[int],
) -> int:
    value = _append_value(runtime, 8, len(positions))
    if value == 0:
        return 0
    index = 0
    while index < len(positions):
        argument_index = argument_start + positions[index]
        item = _call_argument_values[argument_index]
        if not _value_is_valid(runtime, item):
            _scalar_release(runtime, value)
            _fail(
                runtime,
                PORTAPY_INVALID_HANDLE,
                "InvalidHandle",
                "variadic argument is invalid",
                1,
                1,
            )
            return 0
        _value_refs[item] += 1
        _scalar_tuple_item_owner.append(value)
        _scalar_tuple_item_index.append(index)
        _scalar_tuple_item_value.append(item)
        _scalar_release(runtime, item)
        _call_argument_values[argument_index] = 0
        index += 1
    _set_status(PORTAPY_OK)
    return value'''


def _parse_parameters() -> str:
    return r'''def _parse_parameters(source: str, start: int, end: int) -> list[object]:
    original_start = start
    count = 0
    saw_default = False
    saw_slash = False
    saw_star = False
    saw_varargs = False
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
            elif len(text) > 1 and text[0] == "*" and text[1] != "*":
                if saw_star:
                    return ["", item[0], PORTAPY_COMPILE_ERROR]
                name_bounds = _trim(source, item[0] + 1, item[1])
                parsed_name = _parse_identifier_bounds(source, name_bounds[1], name_bounds[0])
                if parsed_name[2] != PORTAPY_OK or parsed_name[0] != name_bounds[0] or parsed_name[1] != name_bounds[1]:
                    return ["", name_bounds[0], PORTAPY_COMPILE_ERROR]
                saw_star = True
                saw_varargs = True
                count += 1
            elif len(text) > 1 and text[0:2] == "**":
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
    if saw_star and not saw_varargs and not keyword_after_star:
        return ["", end, PORTAPY_COMPILE_ERROR]
    return [source[original_start:end], count, PORTAPY_OK]'''


def _varargs_invoke() -> str:
    source = _kind_aware_invoke()
    if _KIND_BINDING_BLOCK not in source:
        raise ValueError("kind-aware argument binder has an unexpected implementation")
    source = source.replace(_KIND_BINDING_BLOCK, _VARARGS_BINDING_BLOCK, 1)
    if _DEFAULT_CONDITION not in source:
        raise ValueError("captured default loop has an unexpected implementation")
    source = source.replace(
        _DEFAULT_CONDITION,
        _VARARGS_DEFAULT_CONDITION,
        1,
    )
    if _RECURSION_END not in source:
        raise ValueError("function recursion guard has an unexpected implementation")
    return source.replace(_RECURSION_END, _VARARGS_PACK_INSERTION, 1)


def rewrite_generated_function_varargs(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    source = _replace_function(source, "_parameter_at", _parameter_at())
    source = _replace_function(source, "_parameter_kind", _parameter_kind())
    source = _replace_function(
        source,
        "_next_positional_parameter",
        _positional_helpers_and_tuple_builder(),
    )
    source = _replace_function(source, "_parse_parameters", _parse_parameters())
    source = _replace_function(source, "_invoke_function", _varargs_invoke())
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function_varargs"]
