"""Combined native expression entry for PortaPy.

The proven range-based boolean parser owns ``not``, comparisons, ``and``, and
``or``. Each scalar operand is delegated to the precedence parser in
``native_api_scalar``. All interpreter semantics remain Python source compiled
by asmpython; native code remains an ABI boundary only.
"""
from __future__ import annotations

from . import native_api_boolean as _boolean
from . import native_api_scalar as _scalar
from .native_api import (
    PORTAPY_COMPILE_ERROR,
    PORTAPY_INVALID_ARGUMENT,
    PORTAPY_INVALID_HANDLE,
    PORTAPY_OK,
    _bind_global,
    _clear_runtime_error,
    _parse_identifier_bounds,
    _runtime_error_line,
    _runtime_is_valid,
    _set_status,
    _skip_space,
    _trim_statement_bounds,
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


def _parse_scalar_complete(runtime: int, source: str, start: int, end: int) -> list[int]:
    bounds = _boolean._trim_range(source, start, end)
    start = bounds[0]
    end = bounds[1]
    parsed = _scalar._parse_comparison(runtime, source, end, start)
    if parsed[2] != PORTAPY_OK:
        return parsed
    final = _skip_space(source, end, parsed[1])
    if final != end:
        _scalar._release(runtime, parsed[0])
        return [0, final, PORTAPY_COMPILE_ERROR]
    return [parsed[0], end, PORTAPY_OK]


# The boolean parser intentionally resolves this helper dynamically. Replacing
# it composes the two Python-authored parser layers without copying semantics
# into C or generated assembly.
_boolean._parse_typed_complete = _parse_scalar_complete


def _parse_expression(runtime: int, source: str, start: int, end: int) -> list[int]:
    return _boolean._parse_boolean_expression(runtime, source, start, end)


def _record_failure(runtime: int, status: int, position: int) -> int:
    return _boolean._record_expression_failure(runtime, status, position)


def _exec_statement(runtime: int, source: str, source_size: int) -> int:
    bounds = _trim_statement_bounds(source, 0, source_size)
    source = source[bounds[0]:bounds[1]]
    source_size = len(source)
    if source_size == 0 or source == "pass":
        return _set_status(PORTAPY_OK)

    assignment = _scalar._find_assignment(source, source_size)
    if assignment[0]:
        left_text = source[0:int(assignment[1])]
        left_bounds = _parse_identifier_bounds(left_text, len(left_text), 0)
        if left_bounds[2] != PORTAPY_OK:
            return _record_failure(runtime, PORTAPY_COMPILE_ERROR, left_bounds[1])
        if _skip_space(left_text, len(left_text), left_bounds[1]) != len(left_text):
            return _record_failure(runtime, PORTAPY_COMPILE_ERROR, left_bounds[1])
        name = left_text[left_bounds[0]:left_bounds[1]]

        right = _parse_expression(runtime, source, int(assignment[2]), source_size)
        if right[2] != PORTAPY_OK:
            return _record_failure(runtime, right[2], right[1])

        if assignment[0] != "=":
            current = _scalar._retain_global(runtime, name, 0)
            if current[2] != PORTAPY_OK:
                _scalar._release(runtime, right[0])
                return _record_failure(runtime, current[2], 0)
            operator = str(assignment[0])[:-1]
            combined = _scalar._binary(
                runtime,
                current[0],
                right[0],
                operator,
                int(assignment[1]),
            )
            if combined[2] != PORTAPY_OK:
                return _record_failure(runtime, combined[2], combined[1])
            right = combined
        return _bind_global(runtime, name, right[0])

    value = _parse_expression(runtime, source, 0, source_size)
    if value[2] != PORTAPY_OK:
        return _record_failure(runtime, value[2], value[1])
    _scalar._release(runtime, value[0])
    return _set_status(PORTAPY_OK)


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    if source_size < 0:
        _boolean._fail(
            runtime,
            PORTAPY_INVALID_ARGUMENT,
            "ValueError",
            "source size cannot be negative",
        )
        return 0
    parsed = _parse_expression(runtime, source, 0, source_size)
    if parsed[2] != PORTAPY_OK:
        _record_failure(runtime, parsed[2], parsed[1])
        return 0
    return parsed[0]


def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    if source_size < 0:
        return _boolean._fail(
            runtime,
            PORTAPY_INVALID_ARGUMENT,
            "ValueError",
            "source size cannot be negative",
        )

    position = 0
    line = 1
    while position < source_size:
        while position < source_size:
            char = source[position]
            if char != ";" and not char.isspace():
                break
            if char == "\n":
                line += 1
            position += 1
        if position >= source_size:
            return _set_status(PORTAPY_OK)

        start = position
        statement_line = line
        quote = ""
        escaped = False
        depth = 0
        while position < source_size:
            char = source[position]
            if quote:
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
                depth -= 1
            elif depth == 0 and (char == ";" or char == "\n" or char == "#"):
                break
            position += 1

        statement = source[start:position]
        status = _exec_statement(runtime, statement, len(statement))
        if status != PORTAPY_OK:
            _runtime_error_line[runtime] = statement_line
            return status

        if position < source_size and source[position] == "#":
            while position < source_size and source[position] != "\n":
                position += 1
        if position < source_size:
            if source[position] == "\n":
                line += 1
            position += 1

    return _set_status(PORTAPY_OK)
