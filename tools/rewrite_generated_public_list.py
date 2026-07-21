"""Add public mutable-list semantics to the final generated native entry."""
from __future__ import annotations

from pathlib import Path


_PUBLIC_LIST_SOURCE = r'''

PORTAPY_VALUE_LIST = 10


def _portapy_list_begin_impl(runtime: int, count: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    if count < 0:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "list size cannot be negative")
        return 0
    value = _append_value(runtime, PORTAPY_VALUE_LIST, count)
    if value == 0:
        return 0
    index = 0
    while index < count:
        _scalar_list_item_owner.append(value)
        _scalar_list_item_index.append(index)
        _scalar_list_item_value.append(0)
        index += 1
    return value


def _portapy_list_initialize_item_impl(
    runtime: int,
    value: int,
    index: int,
    item: int,
) -> int:
    if not _value_is_valid(runtime, value) or not _value_is_valid(runtime, item):
        return _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid list or item handle")
    if _value_kind[value] != PORTAPY_VALUE_LIST:
        return _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not a list")
    size = _scalar_list_size_unchecked(value)
    if index < 0 or index >= size:
        return _fail(runtime, PORTAPY_INVALID_ARGUMENT, "IndexError", "list item index is out of range")
    slot = 1
    while slot < len(_scalar_list_item_owner):
        if (
            _scalar_list_item_owner[slot] == value
            and _scalar_list_item_index[slot] == index
        ):
            if _scalar_list_item_value[slot] != 0:
                return _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "list item was already initialized")
            _value_refs[item] += 1
            _scalar_list_item_value[slot] = item
            return _set_status(PORTAPY_OK)
        slot += 1
    return _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "list item storage is unavailable")


def _portapy_list_finish_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        return _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid list handle")
    if _value_kind[value] != PORTAPY_VALUE_LIST:
        return _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not a list")
    size = _scalar_list_size_unchecked(value)
    index = 0
    while index < size:
        if _scalar_list_item_unchecked(value, index) == 0:
            return _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "list has an uninitialized item")
        index += 1
    return _set_status(PORTAPY_OK)


def _portapy_list_get_size_impl(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid list handle")
        return 0
    if _value_kind[value] != PORTAPY_VALUE_LIST:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not a list")
        return 0
    _set_status(PORTAPY_OK)
    return _scalar_list_size_unchecked(value)


def _portapy_list_get_item_impl(runtime: int, value: int, index: int) -> int:
    if not _value_is_valid(runtime, value):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "invalid list handle")
        return 0
    if _value_kind[value] != PORTAPY_VALUE_LIST:
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "value is not a list")
        return 0
    size = _scalar_list_size_unchecked(value)
    if index < 0 or index >= size:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "IndexError", "list item index is out of range")
        return 0
    item = _scalar_list_item_unchecked(value, index)
    if not _value_is_valid(runtime, item):
        _fail(runtime, PORTAPY_INVALID_HANDLE, "InvalidHandle", "list item is invalid")
        return 0
    _value_refs[item] += 1
    _set_status(PORTAPY_OK)
    return item


def _portapy_list_set_item_impl(
    runtime: int,
    value: int,
    index: int,
    item: int,
) -> int:
    return _scalar_list_set(runtime, value, index, item)


def _portapy_list_append_impl(runtime: int, value: int, item: int) -> int:
    return _scalar_list_append(runtime, value, item)
'''


def rewrite_generated_public_list(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    required = (
        "_scalar_release",
        "_scalar_list_item_owner",
        "_scalar_list_item_index",
        "_scalar_list_item_value",
        "_scalar_list_size_unchecked",
        "_scalar_list_item_unchecked",
        "_scalar_list_set",
        "_scalar_list_append",
    )
    for name in required:
        if name not in source:
            raise ValueError(f"generated host-call entry is missing list dependency {name}")
    if "def _portapy_list_begin_impl(" in source:
        raise ValueError("generated host-call entry already contains public list semantics")
    path.write_text(source.rstrip() + _PUBLIC_LIST_SOURCE + "\n", encoding="utf-8")
    return path


__all__ = ["rewrite_generated_public_list"]
