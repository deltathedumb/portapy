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
_value_runtime: list[int] = [0]
_value_kind: list[int] = [PORTAPY_VALUE_NONE]
_value_i64: list[int] = [0]
_value_refs: list[int] = [0]
_global_runtime: list[int] = [0]
_global_name: list[str] = [""]
_global_value: list[int] = [0]
_last_status: list[int] = [PORTAPY_OK]


def _set_status(status: int) -> int:
    _last_status[0] = status
    return status


def _runtime_is_valid(runtime: int) -> bool:
    return runtime > 0 and runtime < len(_runtime_alive) and _runtime_alive[runtime] == 1


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
    _set_status(PORTAPY_OK)
    return len(_value_refs) - 1


def _find_global_slot(runtime: int, name: str) -> int:
    index = 1
    while index < len(_global_runtime):
        if _global_runtime[index] == runtime and _global_name[index] == name:
            return index
        index += 1
    return 0


def _bind_global(runtime: int, name: str, value: int) -> int:
    if not _value_is_valid(runtime, value):
        return _set_status(PORTAPY_INVALID_HANDLE)
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


def _exec_assignment_span(runtime: int, source: str, source_size: int) -> int:
    bounds = _parse_identifier_bounds(source, source_size, 0)
    if bounds[2] != PORTAPY_OK:
        return _set_status(bounds[2])
    name = source[bounds[0]:bounds[1]]
    position = _skip_space(source, source_size, bounds[1])
    if position >= source_size or source[position] != "=":
        return _set_status(PORTAPY_COMPILE_ERROR)
    parsed = _parse_expression(runtime, source, source_size, position + 1)
    if parsed[2] != PORTAPY_OK:
        return _set_status(parsed[2])
    end = _skip_space(source, source_size, parsed[1])
    if end != source_size:
        return _set_status(PORTAPY_COMPILE_ERROR)
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
    if source_size < 0:
        _set_status(PORTAPY_INVALID_ARGUMENT)
        return 0
    parsed = _parse_expression(runtime, source, source_size, 0)
    if parsed[2] != PORTAPY_OK:
        _set_status(parsed[2])
        return 0
    end = _skip_space(source, source_size, parsed[1])
    if end != source_size:
        _set_status(PORTAPY_COMPILE_ERROR)
        return 0
    return _append_value(runtime, PORTAPY_VALUE_INT, parsed[0])


def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    if source_size < 0:
        return _set_status(PORTAPY_INVALID_ARGUMENT)

    position = 0
    while position < source_size:
        while position < source_size:
            char = source[position]
            if char != ";" and not char.isspace():
                break
            position += 1
        if position >= source_size:
            return _set_status(PORTAPY_OK)

        start = position
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
                return status

        if position < source_size and source[position] == "#":
            while position < source_size and source[position] != "\n":
                position += 1
        if position < source_size:
            position += 1

    return _set_status(PORTAPY_OK)


def _portapy_get_global_span_impl(runtime: int, name: str, name_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    if name_size <= 0:
        _set_status(PORTAPY_INVALID_ARGUMENT)
        return 0
    key = name[0:name_size]
    slot = _find_global_slot(runtime, key)
    if slot == 0:
        _set_status(PORTAPY_NOT_FOUND)
        return 0
    value = _global_value[slot]
    if not _value_is_valid(runtime, value):
        _set_status(PORTAPY_NOT_FOUND)
        return 0
    _value_refs[value] += 1
    _set_status(PORTAPY_OK)
    return value


def _portapy_value_from_none_impl(runtime: int) -> int:
    return _append_value(runtime, PORTAPY_VALUE_NONE, 0)


def _portapy_value_from_bool_impl(runtime: int, value: int) -> int:
    normalized = 0
    if value != 0:
        normalized = 1
    return _append_value(runtime, PORTAPY_VALUE_BOOL, normalized)


def _portapy_value_from_i64_impl(runtime: int, value: int) -> int:
    return _append_value(runtime, PORTAPY_VALUE_INT, value)


def _portapy_value_from_f64_bits_impl(runtime: int, bits: int) -> int:
    return _append_value(runtime, PORTAPY_VALUE_FLOAT, bits)


def _portapy_value_get_kind_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        _set_status(PORTAPY_INVALID_HANDLE)
        return PORTAPY_VALUE_OBJECT
    _set_status(PORTAPY_OK)
    return _value_kind[value]


def _portapy_value_as_bool_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    if _value_kind[value] != PORTAPY_VALUE_BOOL:
        _set_status(PORTAPY_TYPE_ERROR)
        return 0
    _set_status(PORTAPY_OK)
    return _value_i64[value]


def _portapy_value_as_i64_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    if _value_kind[value] != PORTAPY_VALUE_INT:
        _set_status(PORTAPY_TYPE_ERROR)
        return 0
    _set_status(PORTAPY_OK)
    return _value_i64[value]


def _portapy_value_as_f64_bits_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    if _value_kind[value] != PORTAPY_VALUE_FLOAT:
        _set_status(PORTAPY_TYPE_ERROR)
        return 0
    _set_status(PORTAPY_OK)
    return _value_i64[value]


def _portapy_value_retain_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _value_refs[value] += 1
    return _set_status(PORTAPY_OK)


def _portapy_value_release_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _value_refs[value] -= 1
    return _set_status(PORTAPY_OK)
