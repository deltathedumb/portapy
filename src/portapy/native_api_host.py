"""Opaque host objects, global injection, and attribute traversal.

Host objects are represented by stable unsigned 64-bit IDs. The native host
constructs an attribute graph explicitly; PortaPy source can then traverse that
graph with ordinary dotted attribute syntax. This first bridge is deliberately
data-oriented: synchronous calls back into host functions are a separate gate.
"""
from __future__ import annotations

from .native_api import (
    PORTAPY_COMPILE_ERROR,
    PORTAPY_INVALID_ARGUMENT,
    PORTAPY_INVALID_HANDLE,
    PORTAPY_NOT_FOUND,
    PORTAPY_OK,
    PORTAPY_TYPE_ERROR,
    PORTAPY_VALUE_OBJECT,
    _append_value,
    _bind_global,
    _clear_runtime_error,
    _fail,
    _parse_identifier_bounds,
    _runtime_error_line,
    _runtime_is_valid,
    _set_status,
    _skip_space,
    _value_i64,
    _value_is_valid,
    _value_kind,
    _value_refs,
    portapy_abi_version,
    _portapy_error_clear_impl,
    _portapy_error_column_impl,
    _portapy_error_line_impl,
    _portapy_error_message_byte_impl,
    _portapy_error_message_size_impl,
    _portapy_error_status_impl,
    _portapy_error_type_byte_impl,
    _portapy_error_type_size_impl,
    _portapy_get_global_span_impl,
    _portapy_last_status_impl,
    _portapy_runtime_create_impl,
    _portapy_runtime_destroy_impl,
    _portapy_value_as_bool_impl,
    _portapy_value_as_f64_bits_impl,
    _portapy_value_as_i64_impl,
    _portapy_value_from_bool_impl,
    _portapy_value_from_data_begin_impl,
    _portapy_value_from_f64_bits_impl,
    _portapy_value_from_i64_impl,
    _portapy_value_from_none_impl,
    _portapy_value_get_byte_impl,
    _portapy_value_get_kind_impl,
    _portapy_value_get_size_impl,
    _portapy_value_release_impl,
    _portapy_value_retain_impl,
    _portapy_value_set_data_byte_impl,
    _portapy_value_validate_utf8_impl,
)
from .native_api_functions import (
    _parse_call_or_expression as _function_parse_expression,
    _portapy_eval_span_impl as _function_eval_span,
    _portapy_exec_span_impl as _function_exec_span,
)
from .native_api_scalar import (
    _binary,
    _find_assignment,
    _release,
    _retain_global,
)


_host_attr_runtime: list[int] = [0]
_host_attr_owner_id: list[int] = [0]
_host_attr_name: list[str] = [""]
_host_attr_value: list[int] = [0]
_HOST_NOT_PATH = -1


def _trim(source: str, start: int, end: int) -> list[int]:
    while start < end and source[start].isspace():
        start += 1
    while end > start and source[end - 1].isspace():
        end -= 1
    return [start, end]


def _valid_name(source: str, source_size: int) -> bool:
    if source_size <= 0:
        return False
    bounds = _parse_identifier_bounds(source, source_size, 0)
    return bounds[2] == PORTAPY_OK and _skip_space(source, source_size, bounds[1]) == source_size


def _host_object_id(runtime: int, value: int) -> list[int]:
    if not _value_is_valid(runtime, value):
        return [0, PORTAPY_INVALID_HANDLE]
    if _value_kind[value] != PORTAPY_VALUE_OBJECT:
        return [0, PORTAPY_TYPE_ERROR]
    return [_value_i64[value], PORTAPY_OK]


def _find_host_attr(runtime: int, owner_id: int, name: str) -> int:
    index = 1
    while index < len(_host_attr_runtime):
        if (
            _host_attr_runtime[index] == runtime
            and _host_attr_owner_id[index] == owner_id
            and _host_attr_name[index] == name
        ):
            return index
        index += 1
    return 0


def _portapy_value_from_host_object_impl(runtime: int, host_id: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    return _append_value(runtime, PORTAPY_VALUE_OBJECT, host_id)


def _portapy_value_get_host_id_impl(runtime: int, value: int) -> int:
    resolved = _host_object_id(runtime, value)
    if resolved[1] != PORTAPY_OK:
        _set_status(resolved[1])
        return 0
    _set_status(PORTAPY_OK)
    return resolved[0]


def _portapy_set_global_span_impl(
    runtime: int,
    name: str,
    name_size: int,
    value: int,
) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    if name_size <= 0 or not _valid_name(name, name_size):
        return _fail(
            runtime,
            PORTAPY_INVALID_ARGUMENT,
            "ValueError",
            "global name must be a valid identifier",
        )
    if not _value_is_valid(runtime, value):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _value_refs[value] += 1
    status = _bind_global(runtime, name[0:name_size], value)
    if status != PORTAPY_OK:
        _value_refs[value] -= 1
    return status


def _portapy_host_set_attr_span_impl(
    runtime: int,
    owner: int,
    name: str,
    name_size: int,
    value: int,
) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    owner_id = _host_object_id(runtime, owner)
    if owner_id[1] != PORTAPY_OK:
        return _set_status(owner_id[1])
    if name_size <= 0 or not _valid_name(name, name_size):
        return _fail(
            runtime,
            PORTAPY_INVALID_ARGUMENT,
            "ValueError",
            "attribute name must be a valid identifier",
        )
    if not _value_is_valid(runtime, value):
        return _set_status(PORTAPY_INVALID_HANDLE)
    attribute_name = name[0:name_size]
    slot = _find_host_attr(runtime, owner_id[0], attribute_name)
    _value_refs[value] += 1
    if slot == 0:
        _host_attr_runtime.append(runtime)
        _host_attr_owner_id.append(owner_id[0])
        _host_attr_name.append(attribute_name)
        _host_attr_value.append(value)
    else:
        previous = _host_attr_value[slot]
        _host_attr_value[slot] = value
        if _value_is_valid(runtime, previous):
            _value_refs[previous] -= 1
    return _set_status(PORTAPY_OK)


def _portapy_host_get_attr_span_impl(
    runtime: int,
    owner: int,
    name: str,
    name_size: int,
) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    owner_id = _host_object_id(runtime, owner)
    if owner_id[1] != PORTAPY_OK:
        _set_status(owner_id[1])
        return 0
    if name_size <= 0 or not _valid_name(name, name_size):
        _fail(
            runtime,
            PORTAPY_INVALID_ARGUMENT,
            "ValueError",
            "attribute name must be a valid identifier",
        )
        return 0
    slot = _find_host_attr(runtime, owner_id[0], name[0:name_size])
    if slot == 0:
        _fail(
            runtime,
            PORTAPY_NOT_FOUND,
            "AttributeError",
            "host object attribute is not registered",
        )
        return 0
    value = _host_attr_value[slot]
    if not _value_is_valid(runtime, value):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _value_refs[value] += 1
    _set_status(PORTAPY_OK)
    return value


def _dotted_path_bounds(source: str, start: int, end: int) -> list[int]:
    bounds = _trim(source, start, end)
    start = bounds[0]
    end = bounds[1]
    first = _parse_identifier_bounds(source, end, start)
    if first[2] != PORTAPY_OK:
        return [0, start, _HOST_NOT_PATH]
    position = first[1]
    segments = 1
    while True:
        position = _skip_space(source, end, position)
        if position >= end:
            if segments < 2:
                return [0, position, _HOST_NOT_PATH]
            return [segments, position, PORTAPY_OK]
        if source[position] != ".":
            return [0, position, _HOST_NOT_PATH]
        position = _skip_space(source, end, position + 1)
        part = _parse_identifier_bounds(source, end, position)
        if part[2] != PORTAPY_OK:
            return [0, position, PORTAPY_COMPILE_ERROR]
        segments += 1
        position = part[1]


def _resolve_host_path(runtime: int, source: str, start: int, end: int) -> list[int]:
    shape = _dotted_path_bounds(source, start, end)
    if shape[2] != PORTAPY_OK:
        return [0, shape[1], shape[2]]
    bounds = _trim(source, start, end)
    position = bounds[0]
    root = _parse_identifier_bounds(source, bounds[1], position)
    name = source[root[0]:root[1]]
    current = _retain_global(runtime, name, root[1])
    if current[2] != PORTAPY_OK:
        return current
    position = root[1]
    while position < bounds[1]:
        position = _skip_space(source, bounds[1], position)
        if position >= bounds[1]:
            break
        position = _skip_space(source, bounds[1], position + 1)
        part = _parse_identifier_bounds(source, bounds[1], position)
        attribute_name = source[part[0]:part[1]]
        next_value = _portapy_host_get_attr_span_impl(
            runtime,
            current[0],
            attribute_name,
            len(attribute_name),
        )
        _release(runtime, current[0])
        if next_value == 0:
            return [0, part[0], _portapy_last_status_impl()]
        current = [next_value, part[1], PORTAPY_OK]
        position = part[1]
    current[1] = bounds[1]
    return current


def _parse_host_or_function_expression(
    runtime: int,
    source: str,
    start: int,
    end: int,
) -> list[int]:
    shape = _dotted_path_bounds(source, start, end)
    if shape[2] == PORTAPY_OK:
        return _resolve_host_path(runtime, source, start, end)
    if shape[2] != _HOST_NOT_PATH:
        return [0, shape[1], shape[2]]
    return _function_parse_expression(runtime, source, start, end)


def _source_has_host_path(source: str, source_size: int) -> bool:
    position = 0
    while position < source_size:
        line_end = position
        while line_end < source_size and source[line_end] != "\n" and source[line_end] != ";":
            line_end += 1
        bounds = _trim(source, position, line_end)
        if bounds[0] < bounds[1]:
            statement = source[bounds[0]:bounds[1]]
            assignment = _find_assignment(statement, len(statement))
            expression_start = 0
            if assignment[0] != "":
                expression_start = int(assignment[2])
            shape = _dotted_path_bounds(statement, expression_start, len(statement))
            if shape[2] == PORTAPY_OK:
                return True
        position = line_end + 1
    return False


def _operator_from_assignment(assignment: str) -> str:
    if assignment == "+=":
        return "+"
    if assignment == "-=":
        return "-"
    if assignment == "*=":
        return "*"
    if assignment == "//=":
        return "//"
    if assignment == "%=":
        return "%"
    if assignment == "&=":
        return "&"
    if assignment == "^=":
        return "^"
    if assignment == "|=":
        return "|"
    return ""


def _execute_host_statement(runtime: int, statement: str, line: int) -> int:
    bounds = _trim(statement, 0, len(statement))
    statement = statement[bounds[0]:bounds[1]]
    if statement == "" or statement == "pass":
        return _set_status(PORTAPY_OK)
    assignment = _find_assignment(statement, len(statement))
    if assignment[0] == "":
        value = _parse_host_or_function_expression(runtime, statement, 0, len(statement))
        if value[2] != PORTAPY_OK:
            _runtime_error_line[runtime] = line
            return _set_status(value[2])
        _release(runtime, value[0])
        return _set_status(PORTAPY_OK)
    left = statement[0:int(assignment[1])]
    left_bounds = _parse_identifier_bounds(left, len(left), 0)
    if left_bounds[2] != PORTAPY_OK or _skip_space(left, len(left), left_bounds[1]) != len(left):
        return _fail(
            runtime,
            PORTAPY_COMPILE_ERROR,
            "SyntaxError",
            "invalid assignment target",
            line,
            1,
        )
    name = left[left_bounds[0]:left_bounds[1]]
    value = _parse_host_or_function_expression(
        runtime,
        statement,
        int(assignment[2]),
        len(statement),
    )
    if value[2] != PORTAPY_OK:
        _runtime_error_line[runtime] = line
        return _set_status(value[2])
    if assignment[0] != "=":
        current = _retain_global(runtime, name, 0)
        if current[2] != PORTAPY_OK:
            _release(runtime, value[0])
            return _set_status(current[2])
        operator = _operator_from_assignment(assignment[0])
        if operator == "":
            _release(runtime, current[0])
            _release(runtime, value[0])
            return _fail(
                runtime,
                PORTAPY_COMPILE_ERROR,
                "SyntaxError",
                "unsupported augmented assignment",
                line,
                1,
            )
        combined = _binary(runtime, current[0], value[0], operator, int(assignment[1]))
        if combined[2] != PORTAPY_OK:
            return _set_status(combined[2])
        value = combined
    return _bind_global(runtime, name, value[0])


def _exec_host_source(runtime: int, source: str, source_size: int) -> int:
    position = 0
    line = 1
    while position < source_size:
        end = position
        while end < source_size and source[end] != "\n" and source[end] != ";":
            end += 1
        statement = source[position:end]
        status = _execute_host_statement(runtime, statement, line)
        if status != PORTAPY_OK:
            return status
        if end < source_size and source[end] == "\n":
            line += 1
        position = end + 1
    return _set_status(PORTAPY_OK)


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    if source_size < 0:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
        return 0
    shape = _dotted_path_bounds(source, 0, source_size)
    if shape[2] == PORTAPY_OK:
        resolved = _resolve_host_path(runtime, source, 0, source_size)
        if resolved[2] != PORTAPY_OK:
            _set_status(resolved[2])
            return 0
        return resolved[0]
    return _function_eval_span(runtime, source, source_size)


def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    if source_size < 0:
        return _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
    if not _source_has_host_path(source, source_size):
        return _function_exec_span(runtime, source, source_size)
    return _exec_host_source(runtime, source, source_size)
