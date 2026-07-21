"""Bridge hosted Unicode and native byte-oriented source strings."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_tuple_safe import rewrite_generated_tuple as _rewrite


_OLD_PLAIN_CHARACTER = r'''        codepoint = ord(char)
        if kind == PORTAPY_VALUE_BYTES:
            if codepoint > 127:
                return [0, position, PORTAPY_COMPILE_ERROR]
            temporary.append(codepoint)
        else:
            status = _scalar_append_utf8_bytes(temporary, codepoint)
            if status != PORTAPY_OK:
                return [0, position, status]
        position += 1'''

_NEW_PLAIN_CHARACTER = r'''        codepoint = ord(char)
        if kind == PORTAPY_VALUE_BYTES:
            if codepoint > 127:
                return [0, position, PORTAPY_COMPILE_ERROR]
            temporary.append(codepoint)
            position += 1
        else:
            appended = _scalar_append_source_utf8_bytes(
                temporary,
                source,
                source_size,
                position,
            )
            if appended[1] != PORTAPY_OK:
                return [0, position, appended[1]]
            position = appended[0]'''


def _source_utf8_helper() -> str:
    return r'''def _scalar_append_source_utf8_bytes(
    temporary: list[int],
    source: str,
    source_size: int,
    position: int,
) -> list[int]:
    codepoint = ord(source[position])
    expected = 0
    if codepoint >= 194 and codepoint <= 223:
        expected = 1
    elif codepoint >= 224 and codepoint <= 239:
        expected = 2
    elif codepoint >= 240 and codepoint <= 244:
        expected = 3

    if expected > 0 and position + expected < source_size:
        valid = True
        index = 1
        while index <= expected:
            following = ord(source[position + index])
            if following < 128 or following > 191:
                valid = False
            index += 1
        if valid and expected >= 2:
            second = ord(source[position + 1])
            if codepoint == 224 and second < 160:
                valid = False
            if codepoint == 237 and second >= 160:
                valid = False
        if valid and expected == 3:
            second = ord(source[position + 1])
            if codepoint == 240 and second < 144:
                valid = False
            if codepoint == 244 and second > 143:
                valid = False
        if valid:
            index = 0
            while index <= expected:
                temporary.append(ord(source[position + index]))
                index += 1
            return [position + expected + 1, PORTAPY_OK]

    status = _scalar_append_utf8_bytes(temporary, codepoint)
    return [position + 1, status]'''


def rewrite_generated_tuple(path: Path) -> Path:
    _rewrite(path)
    source = path.read_text(encoding="utf-8")
    marker = "def _scalar_parse_data_literal("
    location = source.find(marker)
    if location < 0:
        raise ValueError("generated tuple scalar is missing data literal parser")
    source = source[:location] + _source_utf8_helper() + "\n\n\n" + source[location:]
    if _OLD_PLAIN_CHARACTER not in source:
        raise ValueError("generated tuple scalar has an unexpected character encoder")
    source = source.replace(_OLD_PLAIN_CHARACTER, _NEW_PLAIN_CHARACTER, 1)
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_tuple"]
