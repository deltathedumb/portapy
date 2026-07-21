"""Capture generated native function defaults when ``def`` executes."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_function_arguments import _invoke_function as _call_time_invoke
from tools.rewrite_generated_parser import _replace_function


_CALL_TIME_DEFAULT_BLOCK = r'''            default_bounds = _parameter_default_bounds(parameters, index)
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
            _call_bound_owned[bound_start + index] = 1'''

_CAPTURED_DEFAULT_BLOCK = r'''            captured_default = _find_captured_function_default(slot, index)
            if captured_default == 0:
                _release_call_arguments(runtime, argument_start, argument_count)
                _release_bound_defaults(runtime, bound_start, expected)
                _call_bound_top[0] = bound_start
                return _function_argument_error(
                    runtime,
                    slot,
                    position,
                    "missing required function argument",
                )
            if not _value_is_valid(runtime, captured_default):
                _release_call_arguments(runtime, argument_start, argument_count)
                _release_bound_defaults(runtime, bound_start, expected)
                _call_bound_top[0] = bound_start
                _fail(
                    runtime,
                    PORTAPY_INVALID_HANDLE,
                    "InvalidHandle",
                    "captured default value is no longer valid",
                    _function_definition_line[slot],
                    1,
                )
                return [0, position, PORTAPY_INVALID_HANDLE]
            _value_refs[captured_default] += 1
            _call_bound_values[bound_start + index] = captured_default
            _call_bound_set[bound_start + index] = 1
            _call_bound_owned[bound_start + index] = 1'''


def _capture_helpers_and_register() -> str:
    return r'''def _push_captured_function_default(parameter: int, value: int) -> None:
    top = _captured_default_top[0]
    if top < len(_captured_default_slot):
        _captured_default_slot[top] = 0
        _captured_default_parameter[top] = parameter
        _captured_default_value[top] = value
    else:
        _captured_default_slot.append(0)
        _captured_default_parameter.append(parameter)
        _captured_default_value.append(value)
    _captured_default_top[0] = top + 1


def _release_captured_default_range(runtime: int, start: int) -> None:
    index = start
    while index < _captured_default_top[0]:
        value = _captured_default_value[index]
        if _value_is_valid(runtime, value):
            _value_refs[value] -= 1
        _captured_default_slot[index] = 0
        _captured_default_parameter[index] = 0
        _captured_default_value[index] = 0
        index += 1
    _captured_default_top[0] = start


def _release_function_defaults(runtime: int, slot: int) -> None:
    index = 1
    while index < _captured_default_top[0]:
        if _captured_default_slot[index] == slot:
            value = _captured_default_value[index]
            if _value_is_valid(runtime, value):
                _value_refs[value] -= 1
            _captured_default_slot[index] = 0
            _captured_default_parameter[index] = 0
            _captured_default_value[index] = 0
        index += 1


def _commit_captured_function_defaults(start: int, slot: int) -> None:
    index = start
    while index < _captured_default_top[0]:
        _captured_default_slot[index] = slot
        index += 1


def _find_captured_function_default(slot: int, parameter: int) -> int:
    index = 1
    while index < _captured_default_top[0]:
        if (
            _captured_default_slot[index] == slot
            and _captured_default_parameter[index] == parameter
        ):
            return _captured_default_value[index]
        index += 1
    return 0


def _capture_function_defaults(
    runtime: int,
    parameters: str,
    line: int,
) -> list[int]:
    start = _captured_default_top[0]
    count = _parameter_count(parameters)
    index = 0
    while index < count:
        bounds = _parameter_default_bounds(parameters, index)
        if bounds[2] < 0:
            _release_captured_default_range(runtime, start)
            return [start, PORTAPY_COMPILE_ERROR]
        if bounds[2] != 0:
            parsed = _expr_parse_boolean_expression(
                runtime,
                parameters,
                bounds[0],
                bounds[1],
            )
            if parsed[2] != PORTAPY_OK:
                _release_captured_default_range(runtime, start)
                status = _expr_record_expression_failure(
                    runtime,
                    parsed[2],
                    parsed[1],
                )
                _runtime_error_line[runtime] = line
                return [start, status]
            _push_captured_function_default(index, parsed[0])
        index += 1
    return [start, PORTAPY_OK]


def _register_function(runtime: int, name: str, parameters: str, body: str, line: int) -> int:
    captured = _capture_function_defaults(runtime, parameters, line)
    capture_start = captured[0]
    if captured[1] != PORTAPY_OK:
        return captured[1]

    slot = 1
    while slot < len(_function_runtime):
        if _function_runtime[slot] == runtime and _function_name[slot] == name:
            value = _append_value(runtime, PORTAPY_VALUE_CALLABLE, slot)
            if value == 0:
                _release_captured_default_range(runtime, capture_start)
                return _last_status_value()
            status = _bind_global(runtime, name, value)
            if status != PORTAPY_OK:
                _release_captured_default_range(runtime, capture_start)
                return status
            _release_function_defaults(runtime, slot)
            _function_parameters[slot] = parameters
            _function_body[slot] = body
            _function_definition_line[slot] = line
            _commit_captured_function_defaults(capture_start, slot)
            return status
        slot += 1

    _function_runtime.append(runtime)
    _function_name.append(name)
    _function_parameters.append(parameters)
    _function_body.append(body)
    _function_definition_line.append(line)
    slot = len(_function_runtime) - 1
    value = _append_value(runtime, PORTAPY_VALUE_CALLABLE, slot)
    if value == 0:
        _function_runtime[slot] = 0
        _function_name[slot] = ""
        _function_parameters[slot] = ""
        _function_body[slot] = ""
        _function_definition_line[slot] = 0
        _release_captured_default_range(runtime, capture_start)
        return _last_status_value()
    status = _bind_global(runtime, name, value)
    if status != PORTAPY_OK:
        _function_runtime[slot] = 0
        _function_name[slot] = ""
        _function_parameters[slot] = ""
        _function_body[slot] = ""
        _function_definition_line[slot] = 0
        _release_captured_default_range(runtime, capture_start)
        return status
    _commit_captured_function_defaults(capture_start, slot)
    return status'''


def _captured_invoke_function() -> str:
    source = _call_time_invoke()
    if _CALL_TIME_DEFAULT_BLOCK not in source:
        raise ValueError("call-time default binder has an unexpected implementation")
    return source.replace(_CALL_TIME_DEFAULT_BLOCK, _CAPTURED_DEFAULT_BLOCK, 1)


def rewrite_generated_function_default_capture(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    marker = "_call_bound_top: list[int] = [1]\n"
    if marker not in source:
        raise ValueError("generated function entry is missing bound argument state")
    source = source.replace(
        marker,
        marker
        + "_captured_default_slot: list[int] = [0]\n"
        + "_captured_default_parameter: list[int] = [0]\n"
        + "_captured_default_value: list[int] = [0]\n"
        + "_captured_default_top: list[int] = [1]\n",
        1,
    )
    source = _replace_function(
        source,
        "_register_function",
        _capture_helpers_and_register(),
    )
    source = _replace_function(
        source,
        "_invoke_function",
        _captured_invoke_function(),
    )
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function_default_capture"]
