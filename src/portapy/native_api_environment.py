"""Native environment-management helpers for the full PortaPy artifact.

These helpers expose the interpreter-owned global table to the high-level
binary adapter without moving namespace semantics into C.
"""
from __future__ import annotations

from .native_api import (
    PORTAPY_INVALID_ARGUMENT,
    PORTAPY_INVALID_HANDLE,
    PORTAPY_NOT_FOUND,
    PORTAPY_OK,
    _clear_runtime_error,
    _fail,
    _find_global_slot,
    _global_name,
    _global_runtime,
    _global_value,
    _runtime_is_valid,
    _set_status,
    _value_is_valid,
    _value_refs,
)


def _active_global_slot(runtime: int, logical_index: int) -> int:
    if logical_index < 0:
        return 0
    seen = 0
    slot = 1
    while slot < len(_global_runtime):
        if _global_runtime[slot] == runtime and _global_name[slot] != "":
            if seen == logical_index:
                return slot
            seen += 1
        slot += 1
    return 0


def _portapy_delete_global_span_impl(
    runtime: int,
    name: str,
    name_size: int,
) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    if name_size <= 0 or name_size != len(name):
        return _fail(
            runtime,
            PORTAPY_INVALID_ARGUMENT,
            "ValueError",
            "global name must be a non-empty exact span",
        )
    slot = _find_global_slot(runtime, name)
    if slot == 0:
        return _fail(
            runtime,
            PORTAPY_NOT_FOUND,
            "NameError",
            "global is not defined",
        )
    value = _global_value[slot]
    if _value_is_valid(runtime, value):
        _value_refs[value] -= 1
    _global_runtime[slot] = 0
    _global_name[slot] = ""
    _global_value[slot] = 0
    return _set_status(PORTAPY_OK)


def _portapy_global_count_impl(runtime: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    count = 0
    slot = 1
    while slot < len(_global_runtime):
        if _global_runtime[slot] == runtime and _global_name[slot] != "":
            count += 1
        slot += 1
    _set_status(PORTAPY_OK)
    return count


def _portapy_global_name_size_impl(runtime: int, logical_index: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    slot = _active_global_slot(runtime, logical_index)
    if slot == 0:
        _set_status(PORTAPY_NOT_FOUND)
        return 0
    _set_status(PORTAPY_OK)
    return len(_global_name[slot])


def _portapy_global_name_byte_impl(
    runtime: int,
    logical_index: int,
    byte_index: int,
) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    slot = _active_global_slot(runtime, logical_index)
    if slot == 0:
        _set_status(PORTAPY_NOT_FOUND)
        return 0
    encoded = _global_name[slot].encode("utf-8")
    if byte_index < 0 or byte_index >= len(encoded):
        _set_status(PORTAPY_INVALID_ARGUMENT)
        return 0
    _set_status(PORTAPY_OK)
    return encoded[byte_index]
