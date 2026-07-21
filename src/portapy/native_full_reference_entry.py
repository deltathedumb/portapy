"""Full PortaPy Runtime exposed through native ABI implementation functions.

This entry preserves the stable integer runtime/value handles while delegating
execution, values, globals, calls, and errors to ``reference_api.Runtime``—the
same full frontend/bytecode VM used by the hosted package.
"""
from __future__ import annotations

from .reference_api import Runtime, Status, ValueKind


_runtimes: list[Runtime | None] = [None]
_last_status: list[int] = [int(Status.OK)]


def _set_status(status: object) -> int:
    value = int(status)
    _last_status[0] = value
    return value


def _runtime(runtime: int) -> Runtime | None:
    if runtime <= 0 or runtime >= len(_runtimes):
        return None
    return _runtimes[runtime]


def _portapy_last_status_impl() -> int:
    return _last_status[0]


def _portapy_runtime_create_impl() -> int:
    _runtimes.append(Runtime())
    _set_status(Status.OK)
    return len(_runtimes) - 1


def _portapy_runtime_destroy_impl(runtime: int) -> int:
    instance = _runtime(runtime)
    if instance is None:
        return _set_status(Status.INVALID_HANDLE)
    status = instance.close()
    _runtimes[runtime] = None
    return _set_status(status)


def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    instance = _runtime(runtime)
    if instance is None:
        return _set_status(Status.INVALID_HANDLE)
    if source_size < 0 or source_size > len(source):
        return _set_status(Status.INVALID_ARGUMENT)
    return _set_status(instance.exec_utf8(source[0:source_size]))


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    instance = _runtime(runtime)
    if instance is None:
        _set_status(Status.INVALID_HANDLE)
        return 0
    if source_size < 0 or source_size > len(source):
        _set_status(Status.INVALID_ARGUMENT)
        return 0
    status, value = instance.eval_utf8(source[0:source_size])
    _set_status(status)
    return value


def _portapy_get_global_span_impl(runtime: int, name: str, name_size: int) -> int:
    instance = _runtime(runtime)
    if instance is None:
        _set_status(Status.INVALID_HANDLE)
        return 0
    if name_size <= 0 or name_size > len(name):
        _set_status(Status.INVALID_ARGUMENT)
        return 0
    status, value = instance.get_global(name[0:name_size])
    _set_status(status)
    return value


def _portapy_set_global_span_impl(
    runtime: int,
    name: str,
    name_size: int,
    value: int,
) -> int:
    instance = _runtime(runtime)
    if instance is None:
        return _set_status(Status.INVALID_HANDLE)
    if name_size <= 0 or name_size > len(name):
        return _set_status(Status.INVALID_ARGUMENT)
    status, unboxed = instance.unbox(value)
    if status is not Status.OK:
        return _set_status(status)
    return _set_status(instance.set_global(name[0:name_size], unboxed))


def _portapy_value_from_none_impl(runtime: int) -> int:
    instance = _runtime(runtime)
    if instance is None:
        _set_status(Status.INVALID_HANDLE)
        return 0
    status, value = instance.box_none()
    _set_status(status)
    return value


def _portapy_value_from_bool_impl(runtime: int, value: int) -> int:
    instance = _runtime(runtime)
    if instance is None:
        _set_status(Status.INVALID_HANDLE)
        return 0
    status, result = instance.box_bool(value != 0)
    _set_status(status)
    return result


def _portapy_value_from_i64_impl(runtime: int, value: int) -> int:
    instance = _runtime(runtime)
    if instance is None:
        _set_status(Status.INVALID_HANDLE)
        return 0
    status, result = instance.box_int(value)
    _set_status(status)
    return result


def _portapy_value_get_kind_impl(runtime: int, value: int) -> int:
    instance = _runtime(runtime)
    if instance is None:
        _set_status(Status.INVALID_HANDLE)
        return int(ValueKind.OBJECT)
    status, kind = instance.value_kind(value)
    _set_status(status)
    return int(kind)


def _portapy_value_as_i64_impl(runtime: int, value: int) -> int:
    instance = _runtime(runtime)
    if instance is None:
        _set_status(Status.INVALID_HANDLE)
        return 0
    status, result = instance.as_int(value)
    _set_status(status)
    return result


def _portapy_value_retain_impl(runtime: int, value: int) -> int:
    instance = _runtime(runtime)
    if instance is None:
        return _set_status(Status.INVALID_HANDLE)
    return _set_status(instance.retain(value))


def _portapy_value_release_impl(runtime: int, value: int) -> int:
    instance = _runtime(runtime)
    if instance is None:
        return _set_status(Status.INVALID_HANDLE)
    return _set_status(instance.release(value))


def portapy_abi_version() -> int:
    return 1
