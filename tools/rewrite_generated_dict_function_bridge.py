"""Expose dictionary construction helpers needed by native function binding."""
from __future__ import annotations

from pathlib import Path


_HELPER = r'''def _scalar_string_from_text(runtime: int, text: str) -> int:
    temporary: list[int] = []
    position = 0
    while position < len(text):
        codepoint = ord(text[position])
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
        position += 1
    value = _append_data_value(runtime, PORTAPY_VALUE_STRING, len(temporary))
    if value == 0:
        return 0
    index = 0
    while index < len(temporary):
        status = _set_data_byte(runtime, value, index, temporary[index])
        if status != PORTAPY_OK:
            _scalar_release(runtime, value)
            return 0
        index += 1
    _set_status(PORTAPY_OK)
    return value'''


def rewrite_generated_dict_function_bridge(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    marker = "def _scalar_dict_size_unchecked("
    location = source.find(marker)
    if location < 0:
        raise ValueError("generated dictionary scalar is missing size helper")
    source = source[:location] + _HELPER + "\n\n\n" + source[location:]
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_dict_function_bridge"]
