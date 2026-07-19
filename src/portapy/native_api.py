"""Python-authored core for PortaPy's native opaque-handle ABI.

Every ownership and validation rule in this module is interpreter/product
semantics and therefore remains Python source compiled by asmpython. Platform
assembly wrappers only adapt C pointers, out-parameters, and calling conventions.
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
    return _set_status(PORTAPY_OK)


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
