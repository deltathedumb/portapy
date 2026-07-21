"""Finalize generated tuple scalars with UTF-8 source literals."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function
from tools.rewrite_generated_tuple import rewrite_generated_tuple as _rewrite


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
    return left == right'''


def _data_literal_helpers() -> str:
    return r'''def _scalar_hex_digit(char: str) -> int:
    code = ord(char)
    if code >= 48 and code <= 57:
        return code - 48
    if code >= 65 and code <= 70:
        return code - 55
    if code >= 97 and code <= 102:
        return code - 87
    return -1


def _scalar_append_utf8_bytes(temporary: list[int], codepoint: int) -> int:
    if codepoint < 0 or codepoint > 1114111 or (
        codepoint >= 55296 and codepoint <= 57343
    ):
        return PORTAPY_COMPILE_ERROR
    if codepoint < 128:
        temporary.append(codepoint)
    elif codepoint < 2048:
        temporary.append(192 | (codepoint >> 6))
        temporary.append(128 | (codepoint & 63))
    elif codepoint < 65536:
        temporary.append(224 | (codepoint >> 12))
        temporary.append(128 | ((codepoint >> 6) & 63))
        temporary.append(128 | (codepoint & 63))
    else:
        temporary.append(240 | (codepoint >> 18))
        temporary.append(128 | ((codepoint >> 12) & 63))
        temporary.append(128 | ((codepoint >> 6) & 63))
        temporary.append(128 | (codepoint & 63))
    return PORTAPY_OK


def _scalar_parse_data_literal(
    runtime: int,
    source: str,
    source_size: int,
    position: int,
) -> list[int]:
    position = _skip_space(source, source_size, position)
    kind = PORTAPY_VALUE_STRING
    if position < source_size and (source[position] == "b" or source[position] == "B"):
        if position + 1 >= source_size or (
            source[position + 1] != "'" and source[position + 1] != '"'
        ):
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
        char = source[position]
        if char == quote:
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
                status = _portapy_value_validate_utf8_impl(runtime, value)
                if status != PORTAPY_OK:
                    _value_refs[value] -= 1
                    return [0, position, status]
            return [value, position, PORTAPY_OK]

        if char == "\\":
            position += 1
            if position >= source_size:
                return [0, position, PORTAPY_COMPILE_ERROR]
            escaped = source[position]
            byte = -1
            if escaped == "n":
                byte = 10
            elif escaped == "r":
                byte = 13
            elif escaped == "t":
                byte = 9
            elif escaped == "0":
                byte = 0
            elif escaped == "\\" or escaped == "'" or escaped == '"':
                byte = ord(escaped)
            elif escaped == "x":
                if position + 2 >= source_size:
                    return [0, position, PORTAPY_COMPILE_ERROR]
                high = _scalar_hex_digit(source[position + 1])
                low = _scalar_hex_digit(source[position + 2])
                if high < 0 or low < 0:
                    return [0, position, PORTAPY_COMPILE_ERROR]
                byte = high * 16 + low
                position += 2
            else:
                codepoint = ord(escaped)
                if kind == PORTAPY_VALUE_BYTES and codepoint > 127:
                    return [0, position, PORTAPY_COMPILE_ERROR]
                status = _scalar_append_utf8_bytes(temporary, codepoint)
                if status != PORTAPY_OK:
                    return [0, position, status]
            if byte >= 0:
                temporary.append(byte)
            position += 1
            continue

        codepoint = ord(char)
        if kind == PORTAPY_VALUE_BYTES:
            if codepoint > 127:
                return [0, position, PORTAPY_COMPILE_ERROR]
            temporary.append(codepoint)
        else:
            status = _scalar_append_utf8_bytes(temporary, codepoint)
            if status != PORTAPY_OK:
                return [0, position, status]
        position += 1
    return [0, position, PORTAPY_COMPILE_ERROR]'''


def rewrite_generated_tuple(path: Path) -> Path:
    _rewrite(path)
    source = path.read_text(encoding="utf-8")
    source = _replace_function(source, "_scalar_equal", _equal())
    marker = "def _scalar_parse_atom("
    location = source.find(marker)
    if location < 0:
        raise ValueError("generated tuple scalar is missing atom parser")
    source = source[:location] + _data_literal_helpers() + "\n\n\n" + source[location:]
    source = source.replace(
        "return _parse_data_literal(runtime, source, source_size, position)",
        "return _scalar_parse_data_literal(runtime, source, source_size, position)",
    )
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_tuple"]
