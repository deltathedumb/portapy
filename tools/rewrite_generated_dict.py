"""Add native dictionary literals, ownership, lookup, and equality."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function


_OLD_ATOM_START = r'''    char = source[position]
    if char == "'" or char == '"':'''

_NEW_ATOM_START = r'''    char = source[position]
    if char == "{":
        build_start = _scalar_dict_build_top[0]
        current = _skip_space(source, source_size, position + 1)
        if current < source_size and source[current] == "}":
            value = _scalar_append_dict(runtime, build_start, 0)
            return [value, current + 1, _last_status[0]]
        while True:
            key = _scalar_parse_comparison(runtime, source, source_size, current)
            if key[2] != PORTAPY_OK:
                _scalar_release_dict_build(runtime, build_start)
                return key
            colon = _skip_space(source, source_size, key[1])
            if colon >= source_size or source[colon] != ":":
                _scalar_release(runtime, key[0])
                _scalar_release_dict_build(runtime, build_start)
                return [0, colon, PORTAPY_COMPILE_ERROR]
            item = _scalar_parse_comparison(runtime, source, source_size, colon + 1)
            if item[2] != PORTAPY_OK:
                _scalar_release(runtime, key[0])
                _scalar_release_dict_build(runtime, build_start)
                return item
            _scalar_push_dict_build(key[0], item[0])
            current = _skip_space(source, source_size, item[1])
            if current < source_size and source[current] == "}":
                count = _scalar_dict_build_top[0] - build_start
                value = _scalar_append_dict(runtime, build_start, count)
                return [value, current + 1, _last_status[0]]
            if current >= source_size or source[current] != ",":
                _scalar_release_dict_build(runtime, build_start)
                return [0, current, PORTAPY_COMPILE_ERROR]
            current = _skip_space(source, source_size, current + 1)
            if current < source_size and source[current] == "}":
                count = _scalar_dict_build_top[0] - build_start
                value = _scalar_append_dict(runtime, build_start, count)
                return [value, current + 1, _last_status[0]]
    if char == "'" or char == '"':'''

_OLD_INDEX_BLOCK = r'''        numeric = _scalar_numeric(runtime, index_value[0])
        if numeric[1] != PORTAPY_OK:
            _scalar_release(runtime, left[0])
            _scalar_release(runtime, index_value[0])
            _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "tuple index must be an integer", 1, open_at + 1)
            return [0, open_at, PORTAPY_TYPE_ERROR]
        item = _scalar_tuple_get(runtime, left[0], numeric[0], open_at)
        _scalar_release(runtime, left[0])
        _scalar_release(runtime, index_value[0])'''

_NEW_INDEX_BLOCK = r'''        item = [0, open_at, PORTAPY_TYPE_ERROR]
        if _value_kind[left[0]] == PORTAPY_VALUE_DICT:
            item = _scalar_dict_get(runtime, left[0], index_value[0], open_at)
        else:
            numeric = _scalar_numeric(runtime, index_value[0])
            if numeric[1] != PORTAPY_OK:
                _scalar_release(runtime, left[0])
                _scalar_release(runtime, index_value[0])
                _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "tuple index must be an integer", 1, open_at + 1)
                return [0, open_at, PORTAPY_TYPE_ERROR]
            item = _scalar_tuple_get(runtime, left[0], numeric[0], open_at)
        _scalar_release(runtime, left[0])
        _scalar_release(runtime, index_value[0])'''


def _dict_helpers_and_release() -> str:
    return r'''PORTAPY_VALUE_DICT = 9

_scalar_dict_entry_owner: list[int] = [0]
_scalar_dict_entry_index: list[int] = [0]
_scalar_dict_entry_key: list[int] = [0]
_scalar_dict_entry_value: list[int] = [0]
_scalar_dict_build_keys: list[int] = [0]
_scalar_dict_build_values: list[int] = [0]
_scalar_dict_build_top: list[int] = [1]


def _scalar_release(runtime: int, value: int) -> None:
    if not _value_is_valid(runtime, value):
        return
    _value_refs[value] -= 1
    if _value_refs[value] != 0:
        return
    kind = _value_kind[value]
    if kind == PORTAPY_VALUE_TUPLE:
        index = 1
        while index < len(_scalar_tuple_item_owner):
            if _scalar_tuple_item_owner[index] == value:
                child = _scalar_tuple_item_value[index]
                _scalar_tuple_item_owner[index] = 0
                _scalar_tuple_item_index[index] = 0
                _scalar_tuple_item_value[index] = 0
                _scalar_release(runtime, child)
            index += 1
    elif kind == PORTAPY_VALUE_DICT:
        index = 1
        while index < len(_scalar_dict_entry_owner):
            if _scalar_dict_entry_owner[index] == value:
                key = _scalar_dict_entry_key[index]
                item = _scalar_dict_entry_value[index]
                _scalar_dict_entry_owner[index] = 0
                _scalar_dict_entry_index[index] = 0
                _scalar_dict_entry_key[index] = 0
                _scalar_dict_entry_value[index] = 0
                _scalar_release(runtime, key)
                _scalar_release(runtime, item)
            index += 1


def _scalar_dict_size_unchecked(value: int) -> int:
    return _value_i64[value]


def _scalar_dict_find_entry(value: int, key: int) -> int:
    index = 1
    while index < len(_scalar_dict_entry_owner):
        if (
            _scalar_dict_entry_owner[index] == value
            and _scalar_equal(_scalar_dict_entry_key[index], key)
        ):
            return index
        index += 1
    return 0


def _scalar_dict_get(runtime: int, value: int, key: int, position: int) -> list[int]:
    if not _value_is_valid(runtime, value) or not _value_is_valid(runtime, key):
        return [0, position, PORTAPY_INVALID_HANDLE]
    if _value_kind[value] != PORTAPY_VALUE_DICT:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not subscriptable", 1, position + 1)
        return [0, position, PORTAPY_TYPE_ERROR]
    entry = _scalar_dict_find_entry(value, key)
    if entry == 0:
        _fail(runtime, PORTAPY_RUNTIME_ERROR, "KeyError", "dictionary key was not found", 1, position + 1)
        return [0, position, PORTAPY_RUNTIME_ERROR]
    item = _scalar_dict_entry_value[entry]
    if not _value_is_valid(runtime, item):
        return [0, position, PORTAPY_INVALID_HANDLE]
    _value_refs[item] += 1
    return [item, position, PORTAPY_OK]


def _scalar_push_dict_build(key: int, value: int) -> None:
    top = _scalar_dict_build_top[0]
    if top < len(_scalar_dict_build_keys):
        _scalar_dict_build_keys[top] = key
        _scalar_dict_build_values[top] = value
    else:
        _scalar_dict_build_keys.append(key)
        _scalar_dict_build_values.append(value)
    _scalar_dict_build_top[0] = top + 1


def _scalar_release_dict_build(runtime: int, start: int) -> None:
    index = start
    while index < _scalar_dict_build_top[0]:
        _scalar_release(runtime, _scalar_dict_build_keys[index])
        _scalar_release(runtime, _scalar_dict_build_values[index])
        _scalar_dict_build_keys[index] = 0
        _scalar_dict_build_values[index] = 0
        index += 1
    _scalar_dict_build_top[0] = start


def _scalar_append_dict(runtime: int, start: int, count: int) -> int:
    value = _append_value(runtime, PORTAPY_VALUE_DICT, 0)
    if value == 0:
        _scalar_release_dict_build(runtime, start)
        return 0
    size = 0
    index = 0
    while index < count:
        key = _scalar_dict_build_keys[start + index]
        item = _scalar_dict_build_values[start + index]
        existing = _scalar_dict_find_entry(value, key)
        if existing != 0:
            _scalar_release(runtime, _scalar_dict_entry_value[existing])
            _scalar_release(runtime, key)
            _scalar_dict_entry_value[existing] = item
        else:
            _scalar_dict_entry_owner.append(value)
            _scalar_dict_entry_index.append(size)
            _scalar_dict_entry_key.append(key)
            _scalar_dict_entry_value.append(item)
            size += 1
        _scalar_dict_build_keys[start + index] = 0
        _scalar_dict_build_values[start + index] = 0
        index += 1
    _scalar_dict_build_top[0] = start
    _value_i64[value] = size
    _set_status(PORTAPY_OK)
    return value'''


def _sequence_length() -> str:
    return r'''def _scalar_sequence_length(runtime: int, value: int, position: int) -> list[int]:
    if not _value_is_valid(runtime, value):
        return [0, position, PORTAPY_INVALID_HANDLE]
    kind = _value_kind[value]
    size = 0
    if kind == PORTAPY_VALUE_TUPLE:
        size = _scalar_tuple_size_unchecked(value)
    elif kind == PORTAPY_VALUE_DICT:
        size = _scalar_dict_size_unchecked(value)
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
    if left_kind == 3:
        left_bits = _value_i64[left]
        right_bits = _value_i64[right]
        if (left_bits == 0 or left_bits == -9223372036854775808) and (
            right_bits == 0 or right_bits == -9223372036854775808
        ):
            return True
        return left_bits == right_bits
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
    if left_kind == PORTAPY_VALUE_DICT:
        size = _scalar_dict_size_unchecked(left)
        if _scalar_dict_size_unchecked(right) != size:
            return False
        index = 1
        while index < len(_scalar_dict_entry_owner):
            if _scalar_dict_entry_owner[index] == left:
                matching = _scalar_dict_find_entry(right, _scalar_dict_entry_key[index])
                if matching == 0 or not _scalar_equal(
                    _scalar_dict_entry_value[index],
                    _scalar_dict_entry_value[matching],
                ):
                    return False
            index += 1
        return True
    return left == right'''


def rewrite_generated_dict(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    source = _replace_function(source, "_scalar_release", _dict_helpers_and_release())
    source = _replace_function(source, "_scalar_sequence_length", _sequence_length())
    source = _replace_function(source, "_scalar_equal", _equal())
    if _OLD_ATOM_START not in source:
        raise ValueError("generated scalar atom has an unexpected implementation")
    source = source.replace(_OLD_ATOM_START, _NEW_ATOM_START, 1)
    if _OLD_INDEX_BLOCK not in source:
        raise ValueError("generated scalar indexing has an unexpected implementation")
    source = source.replace(_OLD_INDEX_BLOCK, _NEW_INDEX_BLOCK, 1)
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_dict"]
