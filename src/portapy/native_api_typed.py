"""Typed-literal native source entry for PortaPy.

This module extends the proven native handle/runtime core with a PortaPy-owned
parser for scalar Python literals and typed global assignment. It deliberately
contains interpreter semantics only; the public C boundary remains unchanged.
"""
from __future__ import annotations

from .native_api import (
    PORTAPY_COMPILE_ERROR,
    PORTAPY_INVALID_ARGUMENT,
    PORTAPY_INVALID_HANDLE,
    PORTAPY_NOT_FOUND,
    PORTAPY_OK,
    PORTAPY_RUNTIME_ERROR,
    PORTAPY_TYPE_ERROR,
    PORTAPY_VALUE_BOOL,
    PORTAPY_VALUE_BYTES,
    PORTAPY_VALUE_INT,
    PORTAPY_VALUE_NONE,
    PORTAPY_VALUE_STRING,
    _append_data_value,
    _append_value,
    _bind_global,
    _clear_runtime_error,
    _fail,
    _find_global_slot,
    _global_value,
    _last_status,
    _parse_expression,
    _parse_identifier_bounds,
    _runtime_error_line,
    _runtime_is_valid,
    _set_data_byte,
    _set_status,
    _skip_space,
    _trim_statement_bounds,
    _validate_utf8_value,
    _value_is_valid,
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


def _hex_digit(char: str) -> int:
    code = ord(char)
    if code >= 48 and code <= 57:
        return code - 48
    if code >= 65 and code <= 70:
        return code - 55
    if code >= 97 and code <= 102:
        return code - 87
    return -1


def _literal_byte(source: str, source_size: int, position: int) -> list[int]:
    if position >= source_size:
        return [0, position, PORTAPY_COMPILE_ERROR]
    char = source[position]
    if char != "\\":
        return [ord(char), position + 1, PORTAPY_OK]
    position += 1
    if position >= source_size:
        return [0, position, PORTAPY_COMPILE_ERROR]
    escaped = source[position]
    if escaped == "n":
        return [10, position + 1, PORTAPY_OK]
    if escaped == "r":
        return [13, position + 1, PORTAPY_OK]
    if escaped == "t":
        return [9, position + 1, PORTAPY_OK]
    if escaped == "0":
        return [0, position + 1, PORTAPY_OK]
    if escaped == "\\" or escaped == "'" or escaped == '"':
        return [ord(escaped), position + 1, PORTAPY_OK]
    if escaped == "x":
        if position + 2 >= source_size:
            return [0, position, PORTAPY_COMPILE_ERROR]
        high = _hex_digit(source[position + 1])
        low = _hex_digit(source[position + 2])
        if high < 0 or low < 0:
            return [0, position, PORTAPY_COMPILE_ERROR]
        return [high * 16 + low, position + 3, PORTAPY_OK]
    return [ord(escaped), position + 1, PORTAPY_OK]


def _parse_data_literal(
    runtime: int,
    source: str,
    source_size: int,
    position: int,
) -> list[int]:
    position = _skip_space(source, source_size, position)
    kind = PORTAPY_VALUE_STRING
    if position < source_size and (source[position] == "b" or source[position] == "B"):
        if position + 1 >= source_size:
            return [0, position, PORTAPY_COMPILE_ERROR]
        if source[position + 1] != "'" and source[position + 1] != '"':
            return [0, position, PORTAPY_COMPILE_ERROR]
        kind = PORTAPY_VALUE_BYTES
        position += 1
    if position >= source_size:
        return [0, position, PORTAPY_COMPILE_ERROR]
    quote = source[position]
    if quote != "'" and quote != '"':
        return [0, position, PORTAPY_COMPILE_ERROR]
    position += 1

    temporary: list[int] = []
    while position < source_size:
        if source[position] == quote:
            position += 1
            value = _append_data_value(runtime, kind, len(temporary))
            if value == 0:
                return [0, position, _last_status[0]]
            index = 0
            while index < len(temporary):
                status = _set_data_byte(runtime, value, index, temporary[index])
                if status != PORTAPY_OK:
                    _value_refs[value] -= 1
                    return [0, position, status]
                index += 1
            if kind == PORTAPY_VALUE_STRING:
                status = _validate_utf8_value(runtime, value)
                if status != PORTAPY_OK:
                    _value_refs[value] -= 1
                    return [0, position, status]
            return [value, position, PORTAPY_OK]
        parsed = _literal_byte(source, source_size, position)
        if parsed[2] != PORTAPY_OK:
            return [0, parsed[1], parsed[2]]
        temporary.append(parsed[0])
        position = parsed[1]
    return [0, position, PORTAPY_COMPILE_ERROR]


def _retain_global(runtime: int, name: str, position: int) -> list[int]:
    slot = _find_global_slot(runtime, name)
    if slot == 0:
        return [0, position, PORTAPY_NOT_FOUND]
    value = _global_value[slot]
    if not _value_is_valid(runtime, value):
        return [0, position, PORTAPY_NOT_FOUND]
    _value_refs[value] += 1
    return [value, position, PORTAPY_OK]


def _numeric_value(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    parsed = _parse_expression(runtime, source, source_size, position)
    if parsed[2] != PORTAPY_OK:
        return [0, parsed[1], parsed[2]]
    value = _append_value(runtime, PORTAPY_VALUE_INT, parsed[0])
    if value == 0:
        return [0, parsed[1], _last_status[0]]
    return [value, parsed[1], PORTAPY_OK]


def _parse_typed_expression(
    runtime: int,
    source: str,
    source_size: int,
    position: int,
) -> list[int]:
    position = _skip_space(source, source_size, position)
    if position >= source_size:
        return [0, position, PORTAPY_COMPILE_ERROR]
    char = source[position]
    if char == "'" or char == '"':
        return _parse_data_literal(runtime, source, source_size, position)
    if (char == "b" or char == "B") and position + 1 < source_size:
        if source[position + 1] == "'" or source[position + 1] == '"':
            return _parse_data_literal(runtime, source, source_size, position)
    if char.isalpha() or char == "_":
        bounds = _parse_identifier_bounds(source, source_size, position)
        if bounds[2] != PORTAPY_OK:
            return [0, bounds[1], bounds[2]]
        name = source[bounds[0]:bounds[1]]
        remaining = _skip_space(source, source_size, bounds[1])
        if remaining < source_size:
            return _numeric_value(runtime, source, source_size, position)
        if name == "None":
            value = _append_value(runtime, PORTAPY_VALUE_NONE, 0)
            return [value, bounds[1], _last_status[0]]
        if name == "True":
            value = _append_value(runtime, PORTAPY_VALUE_BOOL, 1)
            return [value, bounds[1], _last_status[0]]
        if name == "False":
            value = _append_value(runtime, PORTAPY_VALUE_BOOL, 0)
            return [value, bounds[1], _last_status[0]]
        return _retain_global(runtime, name, bounds[1])
    return _numeric_value(runtime, source, source_size, position)


def _record_typed_failure(runtime: int, status: int, position: int) -> int:
    if status == PORTAPY_NOT_FOUND:
        return _fail(runtime, status, "NameError", "name is not defined", 1, position + 1)
    if status == PORTAPY_TYPE_ERROR:
        return _fail(runtime, status, "TypeError", "unsupported operand or invalid text literal", 1, position + 1)
    if status == PORTAPY_RUNTIME_ERROR:
        return _fail(runtime, status, "ZeroDivisionError", "integer division or modulo by zero", 1, position + 1)
    return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "invalid PortaPy expression", 1, position + 1)


def _exec_typed_assignment(runtime: int, source: str, source_size: int) -> int:
    bounds = _parse_identifier_bounds(source, source_size, 0)
    if bounds[2] != PORTAPY_OK:
        return _record_typed_failure(runtime, bounds[2], bounds[1])
    name = source[bounds[0]:bounds[1]]
    position = _skip_space(source, source_size, bounds[1])
    if position >= source_size or source[position] != "=":
        return _record_typed_failure(runtime, PORTAPY_COMPILE_ERROR, position)
    parsed = _parse_typed_expression(runtime, source, source_size, position + 1)
    if parsed[2] != PORTAPY_OK:
        return _record_typed_failure(runtime, parsed[2], parsed[1])
    end = _skip_space(source, source_size, parsed[1])
    if end != source_size:
        _value_refs[parsed[0]] -= 1
        return _record_typed_failure(runtime, PORTAPY_COMPILE_ERROR, end)
    return _bind_global(runtime, name, parsed[0])


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    if source_size < 0:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
        return 0
    parsed = _parse_typed_expression(runtime, source, source_size, 0)
    if parsed[2] != PORTAPY_OK:
        _record_typed_failure(runtime, parsed[2], parsed[1])
        return 0
    end = _skip_space(source, source_size, parsed[1])
    if end != source_size:
        _value_refs[parsed[0]] -= 1
        _record_typed_failure(runtime, PORTAPY_COMPILE_ERROR, end)
        return 0
    return parsed[0]


def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    if source_size < 0:
        return _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")

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
            elif char == ";" or char == "\n" or char == "#":
                break
            position += 1
        end = position
        bounds = _trim_statement_bounds(source, start, end)
        if bounds[0] < bounds[1]:
            statement = source[bounds[0]:bounds[1]]
            status = _exec_typed_assignment(runtime, statement, len(statement))
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
