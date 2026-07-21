"""Add owned string-key dictionary values to generated native scalars."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function


_DICT_HELPERS = r'''PORTAPY_VALUE_DICT = 9

_scalar_dict_entry_owner: list[int] = [0]
_scalar_dict_entry_key: list[str] = [""]
_scalar_dict_entry_value: list[int] = [0]


def _scalar_dict_size_unchecked(value: int) -> int:
    return _value_i64[value]


def _scalar_dict_item_unchecked(value: int, key: str) -> int:
    index = 1
    while index < len(_scalar_dict_entry_owner):
        if (
            _scalar_dict_entry_owner[index] == value
            and _scalar_dict_entry_key[index] == key
        ):
            return _scalar_dict_entry_value[index]
        index += 1
    return 0


def _scalar_string_matches_ascii(value: int, text: str) -> bool:
    if _value_kind[value] != PORTAPY_VALUE_STRING:
        return False
    if _value_data_size[value] != len(text):
        return False
    start = _value_data_start[value]
    index = 0
    while index < len(text):
        if _byte_data[start + index] != ord(text[index]):
            return False
        index += 1
    return True


def _scalar_dict_get(
    runtime: int,
    value: int,
    key_value: int,
    position: int,
) -> list[int]:
    if not _value_is_valid(runtime, value) or not _value_is_valid(runtime, key_value):
        return [0, position, PORTAPY_INVALID_HANDLE]
    if _value_kind[value] != PORTAPY_VALUE_DICT:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not a dictionary", 1, position + 1)
        return [0, position, PORTAPY_TYPE_ERROR]
    if _value_kind[key_value] != PORTAPY_VALUE_STRING:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "dictionary key must be a string", 1, position + 1)
        return [0, position, PORTAPY_TYPE_ERROR]
    index = 1
    while index < len(_scalar_dict_entry_owner):
        if (
            _scalar_dict_entry_owner[index] == value
            and _scalar_string_matches_ascii(key_value, _scalar_dict_entry_key[index])
        ):
            child = _scalar_dict_entry_value[index]
            if not _value_is_valid(runtime, child):
                _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "dictionary item is invalid", 1, position + 1)
                return [0, position, PORTAPY_INVALID_HANDLE]
            _value_refs[child] += 1
            return [child, position, PORTAPY_OK]
        index += 1
    _fail(runtime, PORTAPY_NOT_FOUND, "KeyError", "dictionary key was not found", 1, position + 1)
    return [0, position, PORTAPY_NOT_FOUND]
'''


def _release() -> str:
    return r'''def _scalar_release(runtime: int, value: int) -> None:
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
                child = _scalar_dict_entry_value[index]
                _scalar_dict_entry_owner[index] = 0
                _scalar_dict_entry_key[index] = ""
                _scalar_dict_entry_value[index] = 0
                _scalar_release(runtime, child)
            index += 1'''


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
        if _scalar_dict_size_unchecked(left) != _scalar_dict_size_unchecked(right):
            return False
        index = 1
        while index < len(_scalar_dict_entry_owner):
            if _scalar_dict_entry_owner[index] == left:
                key = _scalar_dict_entry_key[index]
                left_item = _scalar_dict_entry_value[index]
                right_item = _scalar_dict_item_unchecked(right, key)
                if right_item == 0 or not _scalar_equal(left_item, right_item):
                    return False
            index += 1
        return True
    return left == right'''


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
        item: list[int]
        if _value_kind[left[0]] == PORTAPY_VALUE_TUPLE:
            numeric = _scalar_numeric(runtime, index_value[0])
            if numeric[1] != PORTAPY_OK:
                _scalar_release(runtime, left[0])
                _scalar_release(runtime, index_value[0])
                _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "tuple index must be an integer", 1, open_at + 1)
                return [0, open_at, PORTAPY_TYPE_ERROR]
            item = _scalar_tuple_get(runtime, left[0], numeric[0], open_at)
        elif _value_kind[left[0]] == PORTAPY_VALUE_DICT:
            item = _scalar_dict_get(runtime, left[0], index_value[0], open_at)
        else:
            _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not subscriptable", 1, open_at + 1)
            item = [0, open_at, PORTAPY_TYPE_ERROR]
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


def rewrite_generated_dict(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    marker = "def _scalar_release("
    location = source.find(marker)
    if location < 0:
        raise ValueError("generated scalar is missing release semantics")
    source = source[:location] + _DICT_HELPERS + "\n\n" + source[location:]
    source = _replace_function(source, "_scalar_release", _release())
    source = _replace_function(source, "_scalar_sequence_length", _sequence_length())
    source = _replace_function(source, "_scalar_equal", _equal())
    source = _replace_function(source, "_scalar_parse_power", _power())
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_dict"]
