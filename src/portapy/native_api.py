"""Python-authored core for PortaPy's native opaque-handle ABI.

Every ownership, validation, parsing, and execution rule in this module is
interpreter semantics and therefore remains Python source compiled by asmpython.
Platform assembly wrappers only adapt C pointers, byte spans, out-parameters,
and calling conventions.
"""
from __future__ import annotations


PORTAPY_OK = 0
PORTAPY_INVALID_ARGUMENT = 1
PORTAPY_COMPILE_ERROR = 2
PORTAPY_RUNTIME_ERROR = 3
PORTAPY_TYPE_ERROR = 4
PORTAPY_NOT_FOUND = 5
PORTAPY_CLOSED = 6
PORTAPY_INVALID_HANDLE = 7
PORTAPY_INTERRUPTED = 8
PORTAPY_ABI_MISMATCH = 9

PORTAPY_VALUE_NONE = 0
PORTAPY_VALUE_BOOL = 1
PORTAPY_VALUE_INT = 2
PORTAPY_VALUE_FLOAT = 3
PORTAPY_VALUE_STRING = 4
PORTAPY_VALUE_BYTES = 5
PORTAPY_VALUE_CALLABLE = 6
PORTAPY_VALUE_OBJECT = 7

_runtime_alive: list[int] = [0]
_runtime_error_status: list[int] = [PORTAPY_OK]
_runtime_error_line: list[int] = [0]
_runtime_error_column: list[int] = [0]
_runtime_error_type: list[str] = [""]
_runtime_error_message: list[str] = [""]

_value_runtime: list[int] = [0]
_value_kind: list[int] = [PORTAPY_VALUE_NONE]
_value_i64: list[int] = [0]
_value_refs: list[int] = [0]
_value_data_start: list[int] = [0]
_value_data_size: list[int] = [0]
_byte_data: list[int] = [0]

_global_runtime: list[int] = [0]
_global_name: list[str] = [""]
_global_value: list[int] = [0]
_last_status: list[int] = [PORTAPY_OK]


def _set_status(status: int) -> int:
    _last_status[0] = status
    return status


def _runtime_is_valid(runtime: int) -> bool:
    return runtime > 0 and runtime < len(_runtime_alive) and _runtime_alive[runtime] == 1


def _clear_runtime_error(runtime: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _runtime_error_status[runtime] = PORTAPY_OK
    _runtime_error_line[runtime] = 0
    _runtime_error_column[runtime] = 0
    _runtime_error_type[runtime] = ""
    _runtime_error_message[runtime] = ""
    return _set_status(PORTAPY_OK)


def _fail(
    runtime: int,
    status: int,
    type_name: str,
    message: str,
    line: int = 0,
    column: int = 0,
) -> int:
    _set_status(status)
    if _runtime_is_valid(runtime):
        _runtime_error_status[runtime] = status
        _runtime_error_line[runtime] = line
        _runtime_error_column[runtime] = column
        _runtime_error_type[runtime] = type_name
        _runtime_error_message[runtime] = message
    return status


def _value_is_valid(runtime: int, value: int) -> bool:
    return (
        _runtime_is_valid(runtime)
        and value > 0
        and value < len(_value_refs)
        and _value_refs[value] > 0
        and _value_runtime[value] == runtime
    )


def _append_value(runtime: int, kind: int, payload: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _value_runtime.append(runtime)
    _value_kind.append(kind)
    _value_i64.append(payload)
    _value_refs.append(1)
    _value_data_start.append(0)
    _value_data_size.append(0)
    _set_status(PORTAPY_OK)
    return len(_value_refs) - 1


def _append_data_value(runtime: int, kind: int, size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    if kind != PORTAPY_VALUE_STRING and kind != PORTAPY_VALUE_BYTES:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "data values must be str or bytes")
        return 0
    if size < 0:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "data size cannot be negative")
        return 0
    start = len(_byte_data)
    index = 0
    while index < size:
        _byte_data.append(0)
        index += 1
    value = _append_value(runtime, kind, 0)
    if value == 0:
        return 0
    _value_data_start[value] = start
    _value_data_size[value] = size
    return value


def _set_data_byte(runtime: int, value: int, index: int, byte: int) -> int:
    if not _value_is_valid(runtime, value):
        return _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid value handle")
    kind = _value_kind[value]
    if kind != PORTAPY_VALUE_STRING and kind != PORTAPY_VALUE_BYTES:
        return _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not str or bytes")
    if index < 0 or index >= _value_data_size[value]:
        return _fail(runtime, PORTAPY_INVALID_ARGUMENT, "IndexError", "data index is out of range")
    if byte < 0 or byte > 255:
        return _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "data byte is out of range")
    _byte_data[_value_data_start[value] + index] = byte
    return _set_status(PORTAPY_OK)


def _validate_utf8_value(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        return _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid value handle")
    if _value_kind[value] != PORTAPY_VALUE_STRING:
        return _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not str")
    start = _value_data_start[value]
    size = _value_data_size[value]
    index = 0
    while index < size:
        first = _byte_data[start + index]
        needed = 0
        minimum = 0
        codepoint = 0
        if first < 128:
            index += 1
            continue
        if first >= 194 and first <= 223:
            needed = 1
            minimum = 128
            codepoint = first - 192
        elif first >= 224 and first <= 239:
            needed = 2
            minimum = 2048
            codepoint = first - 224
        elif first >= 240 and first <= 244:
            needed = 3
            minimum = 65536
            codepoint = first - 240
        else:
            return _fail(runtime, PORTAPY_TYPE_ERROR, "UnicodeDecodeError", "invalid UTF-8 leading byte", 0, index + 1)
        if index + needed >= size:
            return _fail(runtime, PORTAPY_TYPE_ERROR, "UnicodeDecodeError", "truncated UTF-8 sequence", 0, index + 1)
        offset = 1
        while offset <= needed:
            continuation = _byte_data[start + index + offset]
            if continuation < 128 or continuation > 191:
                return _fail(runtime, PORTAPY_TYPE_ERROR, "UnicodeDecodeError", "invalid UTF-8 continuation byte", 0, index + offset + 1)
            codepoint = codepoint * 64 + continuation - 128
            offset += 1
        if codepoint < minimum or codepoint > 1114111 or (codepoint >= 55296 and codepoint <= 57343):
            return _fail(runtime, PORTAPY_TYPE_ERROR, "UnicodeDecodeError", "invalid UTF-8 code point", 0, index + 1)
        index += needed + 1
    return _set_status(PORTAPY_OK)


def _find_global_slot(runtime: int, name: str) -> int:
    index = 1
    while index < len(_global_runtime):
        if _global_runtime[index] == runtime and _global_name[index] == name:
            return index
        index += 1
    return 0


def _bind_global(runtime: int, name: str, value: int) -> int:
    if not _value_is_valid(runtime, value):
        return _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid value handle")
    slot = _find_global_slot(runtime, name)
    if slot != 0:
        old_value = _global_value[slot]
        if _value_is_valid(runtime, old_value):
            _value_refs[old_value] -= 1
        _global_value[slot] = value
        return _set_status(PORTAPY_OK)
    _global_runtime.append(runtime)
    _global_name.append(name)
    _global_value.append(value)
    return _set_status(PORTAPY_OK)


def _lookup_global_i64(runtime: int, name: str) -> list[int]:
    slot = _find_global_slot(runtime, name)
    if slot == 0:
        return [0, PORTAPY_NOT_FOUND]
    value = _global_value[slot]
    if not _value_is_valid(runtime, value):
        return [0, PORTAPY_NOT_FOUND]
    if _value_kind[value] != PORTAPY_VALUE_INT:
        return [0, PORTAPY_TYPE_ERROR]
    return [_value_i64[value], PORTAPY_OK]


def _skip_space(source: str, source_size: int, position: int) -> int:
    while position < source_size and source[position].isspace():
        position += 1
    return position


def _trim_statement_bounds(source: str, start: int, end: int) -> list[int]:
    while start < end and source[start].isspace():
        start += 1
    while end > start and source[end - 1].isspace():
        end -= 1
    return [start, end]


def _parse_identifier_bounds(source: str, source_size: int, position: int) -> list[int]:
    position = _skip_space(source, source_size, position)
    if position >= source_size:
        return [position, position, PORTAPY_COMPILE_ERROR]
    char = source[position]
    if not char.isalpha() and char != "_":
        return [position, position, PORTAPY_COMPILE_ERROR]
    start = position
    position += 1
    while position < source_size:
        char = source[position]
        if not char.isalnum() and char != "_":
            break
        position += 1
    return [start, position, PORTAPY_OK]


def _parse_number(source: str, source_size: int, position: int) -> list[int]:
    position = _skip_space(source, source_size, position)
    start = position
    value = 0
    while position < source_size:
        char = source[position]
        if not char.isdigit():
            break
        value = value * 10 + ord(char) - 48
        position += 1
    if position == start:
        return [0, position, PORTAPY_COMPILE_ERROR]
    return [value, position, PORTAPY_OK]


def _parse_factor(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    position = _skip_space(source, source_size, position)
    if position >= source_size:
        return [0, position, PORTAPY_COMPILE_ERROR]

    char = source[position]
    if char == "+" or char == "-":
        parsed = _parse_factor(runtime, source, source_size, position + 1)
        if parsed[2] != PORTAPY_OK:
            return parsed
        if char == "-":
            parsed[0] = -parsed[0]
        return parsed

    if char == "(":
        parsed = _parse_expression(runtime, source, source_size, position + 1)
        if parsed[2] != PORTAPY_OK:
            return parsed
        end = _skip_space(source, source_size, parsed[1])
        if end >= source_size or source[end] != ")":
            return [0, end, PORTAPY_COMPILE_ERROR]
        parsed[1] = end + 1
        return parsed

    if char.isalpha() or char == "_":
        bounds = _parse_identifier_bounds(source, source_size, position)
        if bounds[2] != PORTAPY_OK:
            return [0, bounds[1], bounds[2]]
        name = source[bounds[0]:bounds[1]]
        found = _lookup_global_i64(runtime, name)
        return [found[0], bounds[1], found[1]]

    return _parse_number(source, source_size, position)


def _parse_term(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    parsed = _parse_factor(runtime, source, source_size, position)
    if parsed[2] != PORTAPY_OK:
        return parsed
    value = parsed[0]
    position = parsed[1]

    while True:
        operator_at = _skip_space(source, source_size, position)
        if operator_at >= source_size:
            return [value, operator_at, PORTAPY_OK]

        operator = source[operator_at]
        operand_at = operator_at + 1
        if operator == "/":
            if operand_at >= source_size or source[operand_at] != "/":
                return [value, operator_at, PORTAPY_OK]
            operand_at += 1
        elif operator != "*" and operator != "%":
            return [value, operator_at, PORTAPY_OK]

        right = _parse_factor(runtime, source, source_size, operand_at)
        if right[2] != PORTAPY_OK:
            return right
        right_value = right[0]
        if operator == "*":
            value = value * right_value
        elif operator == "/":
            if right_value == 0:
                return [0, right[1], PORTAPY_RUNTIME_ERROR]
            value = value // right_value
        else:
            if right_value == 0:
                return [0, right[1], PORTAPY_RUNTIME_ERROR]
            value = value % right_value
        position = right[1]


def _parse_expression(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    parsed = _parse_term(runtime, source, source_size, position)
    if parsed[2] != PORTAPY_OK:
        return parsed
    value = parsed[0]
    position = parsed[1]

    while True:
        operator_at = _skip_space(source, source_size, position)
        if operator_at >= source_size:
            return [value, operator_at, PORTAPY_OK]
        operator = source[operator_at]
        if operator != "+" and operator != "-":
            return [value, operator_at, PORTAPY_OK]

        right = _parse_term(runtime, source, source_size, operator_at + 1)
        if right[2] != PORTAPY_OK:
            return right
        if operator == "+":
            value += right[0]
        else:
            value -= right[0]
        position = right[1]


def _record_parse_failure(runtime: int, status: int, position: int) -> int:
    if status == PORTAPY_NOT_FOUND:
        return _fail(runtime, status, "NameError", "name is not defined", 1, position + 1)
    if status == PORTAPY_TYPE_ERROR:
        return _fail(runtime, status, "TypeError", "integer expression required", 1, position + 1)
    if status == PORTAPY_RUNTIME_ERROR:
        return _fail(runtime, status, "ZeroDivisionError", "integer division or modulo by zero", 1, position + 1)
    return _fail(runtime, status, "SyntaxError", "invalid PortaPy source", 1, position + 1)


def _exec_assignment_span(runtime: int, source: str, source_size: int) -> int:
    bounds = _parse_identifier_bounds(source, source_size, 0)
    if bounds[2] != PORTAPY_OK:
        return _record_parse_failure(runtime, bounds[2], bounds[1])
    name = source[bounds[0]:bounds[1]]
    position = _skip_space(source, source_size, bounds[1])
    if position >= source_size or source[position] != "=":
        return _record_parse_failure(runtime, PORTAPY_COMPILE_ERROR, position)
    parsed = _parse_expression(runtime, source, source_size, position + 1)
    if parsed[2] != PORTAPY_OK:
        return _record_parse_failure(runtime, parsed[2], parsed[1])
    end = _skip_space(source, source_size, parsed[1])
    if end != source_size:
        return _record_parse_failure(runtime, PORTAPY_COMPILE_ERROR, end)
    value = _append_value(runtime, PORTAPY_VALUE_INT, parsed[0])
    if value == 0:
        return _last_status[0]
    return _bind_global(runtime, name, value)


def portapy_abi_version() -> int:
    return 1


def _portapy_last_status_impl() -> int:
    return _last_status[0]


def _portapy_runtime_create_impl() -> int:
    _runtime_alive.append(1)
    _runtime_error_status.append(PORTAPY_OK)
    _runtime_error_line.append(0)
    _runtime_error_column.append(0)
    _runtime_error_type.append("")
    _runtime_error_message.append("")
    _set_status(PORTAPY_OK)
    return len(_runtime_alive) - 1


def _portapy_runtime_destroy_impl(runtime: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _runtime_alive[runtime] = 0
    index = 1
    while index < len(_value_refs):
        if _value_runtime[index] == runtime:
            _value_refs[index] = 0
        index += 1
    index = 1
    while index < len(_global_runtime):
        if _global_runtime[index] == runtime:
            _global_value[index] = 0
        index += 1
    return _set_status(PORTAPY_OK)


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    if source_size < 0:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
        return 0
    parsed = _parse_expression(runtime, source, source_size, 0)
    if parsed[2] != PORTAPY_OK:
        _record_parse_failure(runtime, parsed[2], parsed[1])
        return 0
    end = _skip_space(source, source_size, parsed[1])
    if end != source_size:
        _record_parse_failure(runtime, PORTAPY_COMPILE_ERROR, end)
        return 0
    return _append_value(runtime, PORTAPY_VALUE_INT, parsed[0])


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
        while position < source_size:
            char = source[position]
            if char == ";" or char == "\n" or char == "#":
                break
            position += 1
        end = position
        bounds = _trim_statement_bounds(source, start, end)
        if bounds[0] < bounds[1]:
            statement = source[bounds[0]:bounds[1]]
            status = _exec_assignment_span(runtime, statement, len(statement))
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


def _portapy_get_global_span_impl(runtime: int, name: str, name_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    if name_size <= 0:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "global name cannot be empty")
        return 0
    key = name[0:name_size]
    slot = _find_global_slot(runtime, key)
    if slot == 0:
        _fail(runtime, PORTAPY_NOT_FOUND, "KeyError", "global name was not found")
        return 0
    value = _global_value[slot]
    if not _value_is_valid(runtime, value):
        _fail(runtime, PORTAPY_NOT_FOUND, "KeyError", "global value was not found")
        return 0
    _value_refs[value] += 1
    _set_status(PORTAPY_OK)
    return value


def _portapy_value_from_none_impl(runtime: int) -> int:
    if _runtime_is_valid(runtime):
        _clear_runtime_error(runtime)
    return _append_value(runtime, PORTAPY_VALUE_NONE, 0)


def _portapy_value_from_bool_impl(runtime: int, value: int) -> int:
    if _runtime_is_valid(runtime):
        _clear_runtime_error(runtime)
    normalized = 0
    if value != 0:
        normalized = 1
    return _append_value(runtime, PORTAPY_VALUE_BOOL, normalized)


def _portapy_value_from_i64_impl(runtime: int, value: int) -> int:
    if _runtime_is_valid(runtime):
        _clear_runtime_error(runtime)
    return _append_value(runtime, PORTAPY_VALUE_INT, value)


def _portapy_value_from_f64_bits_impl(runtime: int, bits: int) -> int:
    if _runtime_is_valid(runtime):
        _clear_runtime_error(runtime)
    return _append_value(runtime, PORTAPY_VALUE_FLOAT, bits)


def _portapy_value_from_data_begin_impl(runtime: int, kind: int, size: int) -> int:
    if _runtime_is_valid(runtime):
        _clear_runtime_error(runtime)
    return _append_data_value(runtime, kind, size)


def _portapy_value_set_data_byte_impl(runtime: int, value: int, index: int, byte: int) -> int:
    return _set_data_byte(runtime, value, index, byte)


def _portapy_value_validate_utf8_impl(runtime: int, value: int) -> int:
    return _validate_utf8_value(runtime, value)


def _portapy_value_get_kind_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid value handle")
        return PORTAPY_VALUE_OBJECT
    _set_status(PORTAPY_OK)
    return _value_kind[value]


def _portapy_value_as_bool_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid value handle")
        return 0
    if _value_kind[value] != PORTAPY_VALUE_BOOL:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not bool")
        return 0
    _set_status(PORTAPY_OK)
    return _value_i64[value]


def _portapy_value_as_i64_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid value handle")
        return 0
    if _value_kind[value] != PORTAPY_VALUE_INT:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not int")
        return 0
    _set_status(PORTAPY_OK)
    return _value_i64[value]


def _portapy_value_as_f64_bits_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid value handle")
        return 0
    if _value_kind[value] != PORTAPY_VALUE_FLOAT:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not float")
        return 0
    _set_status(PORTAPY_OK)
    return _value_i64[value]


def _portapy_value_get_size_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid value handle")
        return 0
    kind = _value_kind[value]
    if kind != PORTAPY_VALUE_STRING and kind != PORTAPY_VALUE_BYTES:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not str or bytes")
        return 0
    _set_status(PORTAPY_OK)
    return _value_data_size[value]


def _portapy_value_get_byte_impl(runtime: int, value: int, index: int) -> int:
    if not _value_is_valid(runtime, value):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid value handle")
        return 0
    kind = _value_kind[value]
    if kind != PORTAPY_VALUE_STRING and kind != PORTAPY_VALUE_BYTES:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not str or bytes")
        return 0
    if index < 0 or index >= _value_data_size[value]:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "IndexError", "data index is out of range")
        return 0
    _set_status(PORTAPY_OK)
    return _byte_data[_value_data_start[value] + index]


def _portapy_error_status_impl(runtime: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return PORTAPY_INVALID_HANDLE
    _set_status(PORTAPY_OK)
    return _runtime_error_status[runtime]


def _portapy_error_line_impl(runtime: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _set_status(PORTAPY_OK)
    return _runtime_error_line[runtime]


def _portapy_error_column_impl(runtime: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _set_status(PORTAPY_OK)
    return _runtime_error_column[runtime]


def _portapy_error_type_size_impl(runtime: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _set_status(PORTAPY_OK)
    return len(_runtime_error_type[runtime])


def _portapy_error_type_byte_impl(runtime: int, index: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    value = _runtime_error_type[runtime]
    if index < 0 or index >= len(value):
        _set_status(PORTAPY_INVALID_ARGUMENT)
        return 0
    _set_status(PORTAPY_OK)
    return ord(value[index])


def _portapy_error_message_size_impl(runtime: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _set_status(PORTAPY_OK)
    return len(_runtime_error_message[runtime])


def _portapy_error_message_byte_impl(runtime: int, index: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    value = _runtime_error_message[runtime]
    if index < 0 or index >= len(value):
        _set_status(PORTAPY_INVALID_ARGUMENT)
        return 0
    _set_status(PORTAPY_OK)
    return ord(value[index])


def _portapy_error_clear_impl(runtime: int) -> int:
    return _clear_runtime_error(runtime)


def _portapy_value_retain_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        return _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid value handle")
    _value_refs[value] += 1
    return _set_status(PORTAPY_OK)


def _portapy_value_release_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        return _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid value handle")
    _value_refs[value] -= 1
    return _set_status(PORTAPY_OK)
