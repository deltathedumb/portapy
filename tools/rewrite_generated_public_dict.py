"""Add public string-key dictionary semantics to the final native entry."""
from __future__ import annotations

from pathlib import Path


_PUBLIC_DICT_SOURCE = r'''

PORTAPY_VALUE_DICT = 9


def _portapy_dict_begin_impl(runtime: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    value = _append_value(runtime, PORTAPY_VALUE_DICT, 0)
    return value


def _portapy_dict_set_span_impl(
    runtime: int,
    value: int,
    key: str,
    key_size: int,
    item: int,
) -> int:
    if not _value_is_valid(runtime, value) or not _value_is_valid(runtime, item):
        return _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid dictionary or item handle")
    if _value_kind[value] != PORTAPY_VALUE_DICT:
        return _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not a dictionary")
    if key_size <= 0 or key_size > len(key):
        return _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "dictionary key must be non-empty")
    name = key[:key_size]
    index = 1
    while index < len(_scalar_dict_entry_owner):
        if (
            _scalar_dict_entry_owner[index] == value
            and _scalar_dict_entry_key[index] == name
        ):
            previous = _scalar_dict_entry_value[index]
            _value_refs[item] += 1
            _scalar_dict_entry_value[index] = item
            _scalar_release(runtime, previous)
            return _set_status(PORTAPY_OK)
        index += 1
    _value_refs[item] += 1
    _scalar_dict_entry_owner.append(value)
    _scalar_dict_entry_key.append(name)
    _scalar_dict_entry_value.append(item)
    _value_i64[value] += 1
    return _set_status(PORTAPY_OK)


def _portapy_dict_get_size_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid dictionary handle")
        return 0
    if _value_kind[value] != PORTAPY_VALUE_DICT:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not a dictionary")
        return 0
    _set_status(PORTAPY_OK)
    return _scalar_dict_size_unchecked(value)


def _portapy_dict_storage_index(value: int, wanted: int) -> int:
    current = 0
    index = 1
    while index < len(_scalar_dict_entry_owner):
        if _scalar_dict_entry_owner[index] == value:
            if current == wanted:
                return index
            current += 1
        index += 1
    return 0


def _portapy_dict_key_size_impl(runtime: int, value: int, index: int) -> int:
    if not _value_is_valid(runtime, value):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid dictionary handle")
        return 0
    if _value_kind[value] != PORTAPY_VALUE_DICT:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not a dictionary")
        return 0
    if index < 0 or index >= _scalar_dict_size_unchecked(value):
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "IndexError", "dictionary key index is out of range")
        return 0
    storage = _portapy_dict_storage_index(value, index)
    if storage == 0:
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "dictionary key storage is unavailable")
        return 0
    _set_status(PORTAPY_OK)
    return len(_scalar_dict_entry_key[storage])


def _portapy_dict_key_byte_impl(
    runtime: int,
    value: int,
    index: int,
    offset: int,
) -> int:
    size = _portapy_dict_key_size_impl(runtime, value, index)
    if _last_status[0] != PORTAPY_OK:
        return 0
    if offset < 0 or offset >= size:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "IndexError", "dictionary key byte is out of range")
        return 0
    storage = _portapy_dict_storage_index(value, index)
    _set_status(PORTAPY_OK)
    return ord(_scalar_dict_entry_key[storage][offset])


def _portapy_dict_get_item_span_impl(
    runtime: int,
    value: int,
    key: str,
    key_size: int,
) -> int:
    if not _value_is_valid(runtime, value):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid dictionary handle")
        return 0
    if _value_kind[value] != PORTAPY_VALUE_DICT:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not a dictionary")
        return 0
    if key_size <= 0 or key_size > len(key):
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "dictionary key must be non-empty")
        return 0
    item = _scalar_dict_item_unchecked(value, key[:key_size])
    if not _value_is_valid(runtime, item):
        _fail(runtime, PORTAPY_NOT_FOUND, "KeyError", "dictionary key was not found")
        return 0
    _value_refs[item] += 1
    _set_status(PORTAPY_OK)
    return item
'''


def rewrite_generated_public_dict(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    required = (
        "_scalar_release",
        "_scalar_dict_entry_owner",
        "_scalar_dict_entry_key",
        "_scalar_dict_entry_value",
        "_scalar_dict_size_unchecked",
        "_scalar_dict_item_unchecked",
    )
    for name in required:
        if name not in source:
            raise ValueError(f"generated host-call entry is missing dictionary dependency {name}")
    if "def _portapy_dict_begin_impl(" in source:
        raise ValueError("generated host-call entry already contains public dictionary semantics")
    path.write_text(source.rstrip() + _PUBLIC_DICT_SOURCE + "\n", encoding="utf-8")
    return path


__all__ = ["rewrite_generated_public_dict"]
