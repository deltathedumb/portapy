"""Add immutable tuple semantics to generated native scalar parsers."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function


def _tuple_helpers_and_release() -> str:
    return r'''PORTAPY_VALUE_TUPLE = 8

_scalar_tuple_item_owner: list[int] = [0]
_scalar_tuple_item_index: list[int] = [0]
_scalar_tuple_item_value: list[int] = [0]
_scalar_tuple_build_values: list[int] = [0]
_scalar_tuple_build_top: list[int] = [1]


def _scalar_release(runtime: int, value: int) -> None:
    if not _value_is_valid(runtime, value):
        return
    _value_refs[value] -= 1
    if _value_refs[value] != 0 or _value_kind[value] != PORTAPY_VALUE_TUPLE:
        return
    index = 1
    while index < len(_scalar_tuple_item_owner):
        if _scalar_tuple_item_owner[index] == value:
            child = _scalar_tuple_item_value[index]
            _scalar_tuple_item_owner[index] = 0
            _scalar_tuple_item_index[index] = 0
            _scalar_tuple_item_value[index] = 0
            _scalar_release(runtime, child)
        index += 1


def _scalar_push_tuple_build(value: int) -> None:
    top = _scalar_tuple_build_top[0]
    if top < len(_scalar_tuple_build_values):
        _scalar_tuple_build_values[top] = value
    else:
        _scalar_tuple_build_values.append(value)
    _scalar_tuple_build_top[0] = top + 1


def _scalar_release_tuple_build(runtime: int, start: int) -> None:
    index = start
    while index < _scalar_tuple_build_top[0]:
        _scalar_release(runtime, _scalar_tuple_build_values[index])
        _scalar_tuple_build_values[index] = 0
        index += 1
    _scalar_tuple_build_top[0] = start


def _scalar_append_tuple(runtime: int, start: int, count: int) -> int:
    value = _append_value(runtime, PORTAPY_VALUE_TUPLE, count)
    if value == 0:
        _scalar_release_tuple_build(runtime, start)
        return 0
    index = 0
    while index < count:
        _scalar_tuple_item_owner.append(value)
        _scalar_tuple_item_index.append(index)
        _scalar_tuple_item_value.append(_scalar_tuple_build_values[start + index])
        _scalar_tuple_build_values[start + index] = 0
        index += 1
    _scalar_tuple_build_top[0] = start
    return value


def _scalar_tuple_size_unchecked(value: int) -> int:
    return _value_i64[value]


def _scalar_tuple_item_unchecked(value: int, wanted: int) -> int:
    index = 1
    while index < len(_scalar_tuple_item_owner):
        if (
            _scalar_tuple_item_owner[index] == value
            and _scalar_tuple_item_index[index] == wanted
        ):
            return _scalar_tuple_item_value[index]
        index += 1
    return 0


def _scalar_tuple_get(runtime: int, value: int, wanted: int, position: int) -> list[int]:
    if not _value_is_valid(runtime, value):
        return [0, position, PORTAPY_INVALID_HANDLE]
    if _value_kind[value] != PORTAPY_VALUE_TUPLE:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not subscriptable", 1, position + 1)
        return [0, position, PORTAPY_TYPE_ERROR]
    size = _scalar_tuple_size_unchecked(value)
    if wanted < 0:
        wanted += size
    if wanted < 0 or wanted >= size:
        _fail(runtime, PORTAPY_RUNTIME_ERROR, "IndexError", "tuple index out of range", 1, position + 1)
        return [0, position, PORTAPY_RUNTIME_ERROR]
    child = _scalar_tuple_item_unchecked(value, wanted)
    if not _value_is_valid(runtime, child):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "tuple item is invalid", 1, position + 1)
        return [0, position, PORTAPY_INVALID_HANDLE]
    _value_refs[child] += 1
    return [child, position, PORTAPY_OK]


def _scalar_sequence_length(runtime: int, value: int, position: int) -> list[int]:
    if not _value_is_valid(runtime, value):
        return [0, position, PORTAPY_INVALID_HANDLE]
    kind = _value_kind[value]
    size = 0
    if kind == PORTAPY_VALUE_TUPLE:
        size = _scalar_tuple_size_unchecked(value)
    elif kind == PORTAPY_VALUE_BYTES:
        size = _value_data_size[value]
    elif kind == PORTAPY_VALUE_STRING:
        start = _value_data_start[value]
        end = start + _value_data_size[value]
        index = start
        while index < end:
            byte = _byte_data[index]
            if byte < 128 or byte >= 192:
                size += 1
            index += 1
    else:
        _scalar_release(runtime, value)
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "object has no len()", 1, position + 1)
        return [0, position, PORTAPY_TYPE_ERROR]
    _scalar_release(runtime, value)
    result = _append_value(runtime, PORTAPY_VALUE_INT, size)
    return [result, position, _last_status[0]]'''


def _equal() -> str:
    return r'''def _scalar_equal(left: int, right: int) -> bool:
    left_kind = _value_kind[left]
    right_kind = _value_kind[right]
    if (left_kind == PORTAPY_VALUE_INT or left_kind == PORTAPY_VALUE_BOOL) and (
        right_kind == PORTAPY_VALUE_INT or right_kind == PORTAPY_VALUE_BOOL
    ):
        return _value_i64[left] == _value_i64[right]
    if left_kind != right_kind:
        return False
    if left_kind == PORTAPY_VALUE_NONE:
        return True
    if left_kind == PORTAPY_VALUE_STRING or left_kind == PORTAPY_VALUE_BYTES:
        return _scalar_data_order(left, right) == 0
    if left_kind == PORTAPY_VALUE_TUPLE:
        size = _scalar_tuple_size_unchecked(left)
        if _scalar_tuple_size_unchecked(right) != size:
            return False
        index = 0
        while index < size:
            left_item = _scalar_tuple_item_unchecked(left, index)
            right_item = _scalar_tuple_item_unchecked(right, index)
            if left_item == 0 or right_item == 0 or not _scalar_equal(left_item, right_item):
                return False
            index += 1
        return True
    return left == right'''


def _atom() -> str:
    return r'''def _scalar_parse_atom(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    position = _skip_space(source, source_size, position)
    if position >= source_size:
        return [0, position, PORTAPY_COMPILE_ERROR]
    char = source[position]
    if char == "'" or char == '"':
        return _parse_data_literal(runtime, source, source_size, position)
    if (char == "b" or char == "B") and position + 1 < source_size and (
        source[position + 1] == "'" or source[position + 1] == '"'
    ):
        return _parse_data_literal(runtime, source, source_size, position)
    if char == "(":
        inside = _skip_space(source, source_size, position + 1)
        if inside < source_size and source[inside] == ")":
            value = _scalar_append_tuple(runtime, _scalar_tuple_build_top[0], 0)
            return [value, inside + 1, _last_status[0]]
        first = _scalar_parse_comparison(runtime, source, source_size, position + 1)
        if first[2] != PORTAPY_OK:
            return first
        separator = _skip_space(source, source_size, first[1])
        if separator < source_size and source[separator] == ")":
            first[1] = separator + 1
            return first
        if separator >= source_size or source[separator] != ",":
            _scalar_release(runtime, first[0])
            return [0, separator, PORTAPY_COMPILE_ERROR]
        build_start = _scalar_tuple_build_top[0]
        _scalar_push_tuple_build(first[0])
        current = separator + 1
        while True:
            current = _skip_space(source, source_size, current)
            if current < source_size and source[current] == ")":
                count = _scalar_tuple_build_top[0] - build_start
                value = _scalar_append_tuple(runtime, build_start, count)
                return [value, current + 1, _last_status[0]]
            item = _scalar_parse_comparison(runtime, source, source_size, current)
            if item[2] != PORTAPY_OK:
                _scalar_release_tuple_build(runtime, build_start)
                return item
            _scalar_push_tuple_build(item[0])
            current = _skip_space(source, source_size, item[1])
            if current < source_size and source[current] == ")":
                count = _scalar_tuple_build_top[0] - build_start
                value = _scalar_append_tuple(runtime, build_start, count)
                return [value, current + 1, _last_status[0]]
            if current >= source_size or source[current] != ",":
                _scalar_release_tuple_build(runtime, build_start)
                return [0, current, PORTAPY_COMPILE_ERROR]
            current += 1
    if char.isdigit():
        parsed = _parse_number(source, source_size, position)
        if parsed[2] != PORTAPY_OK:
            return [0, parsed[1], parsed[2]]
        value = _append_value(runtime, PORTAPY_VALUE_INT, parsed[0])
        return [value, parsed[1], _last_status[0]]
    if char.isalpha() or char == "_":
        bounds = _parse_identifier_bounds(source, source_size, position)
        if bounds[2] != PORTAPY_OK:
            return [0, bounds[1], bounds[2]]
        name = source[bounds[0]:bounds[1]]
        after = _skip_space(source, source_size, bounds[1])
        if name == "len" and after < source_size and source[after] == "(":
            argument = _scalar_parse_comparison(runtime, source, source_size, after + 1)
            if argument[2] != PORTAPY_OK:
                return argument
            close = _skip_space(source, source_size, argument[1])
            if close >= source_size or source[close] != ")":
                _scalar_release(runtime, argument[0])
                return [0, close, PORTAPY_COMPILE_ERROR]
            result = _scalar_sequence_length(runtime, argument[0], bounds[0])
            result[1] = close + 1
            return result
        if name == "None":
            value = _append_value(runtime, PORTAPY_VALUE_NONE, 0)
            return [value, bounds[1], _last_status[0]]
        if name == "True" or name == "False":
            value = _append_value(runtime, PORTAPY_VALUE_BOOL, 1 if name == "True" else 0)
            return [value, bounds[1], _last_status[0]]
        return _scalar_retain_global(runtime, name, bounds[1])
    return [0, position, PORTAPY_COMPILE_ERROR]'''


def _power() -> str:
    return r'''def _scalar_parse_power(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    left = _scalar_parse_atom(runtime, source, source_size, position)
    if left[2] != PORTAPY_OK:
        return left
    while True:
        open_at = _skip_space(source, source_size, left[1])
        if open_at >= source_size or source[open_at] != "[":
            break
        index_value = _scalar_parse_comparison(runtime, source, source_size, open_at + 1)
        if index_value[2] != PORTAPY_OK:
            _scalar_release(runtime, left[0])
            return index_value
        close = _skip_space(source, source_size, index_value[1])
        if close >= source_size or source[close] != "]":
            _scalar_release(runtime, left[0])
            _scalar_release(runtime, index_value[0])
            return [0, close, PORTAPY_COMPILE_ERROR]
        numeric = _scalar_numeric(runtime, index_value[0])
        if numeric[1] != PORTAPY_OK:
            _scalar_release(runtime, left[0])
            _scalar_release(runtime, index_value[0])
            _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "tuple index must be an integer", 1, open_at + 1)
            return [0, open_at, PORTAPY_TYPE_ERROR]
        item = _scalar_tuple_get(runtime, left[0], numeric[0], open_at)
        _scalar_release(runtime, left[0])
        _scalar_release(runtime, index_value[0])
        if item[2] != PORTAPY_OK:
            return item
        item[1] = close + 1
        left = item
    operator_at = _skip_space(source, source_size, left[1])
    if operator_at + 1 < source_size and source[operator_at:operator_at + 2] == "**":
        right = _scalar_parse_unary(runtime, source, source_size, operator_at + 2)
        if right[2] != PORTAPY_OK:
            _scalar_release(runtime, left[0])
            return right
        result = _scalar_binary(runtime, left[0], right[0], "**", operator_at)
        result[1] = right[1]
        return result
    return left'''


def rewrite_generated_tuple(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    source = _replace_function(source, "_scalar_release", _tuple_helpers_and_release())
    source = _replace_function(source, "_scalar_equal", _equal())
    source = _replace_function(source, "_scalar_parse_atom", _atom())
    source = _replace_function(source, "_scalar_parse_power", _power())
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_tuple"]
