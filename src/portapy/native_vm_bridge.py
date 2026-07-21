"""Bridge the stable native handle ABI to PortaPy's standalone frontend and VM.

This module is Python-authored interpreter glue intended to be compiled by
asmpython. It deliberately reuses the existing runtime, value, global, host
object, and host-call tables so the full VM can replace the incremental source
executor without changing the public C ABI.
"""
from __future__ import annotations

from .core.frontend import compile_source
from .core.vm import VirtualMachine
from .native_api import (
    PORTAPY_COMPILE_ERROR,
    PORTAPY_INVALID_HANDLE,
    PORTAPY_OK,
    PORTAPY_RUNTIME_ERROR,
    PORTAPY_TYPE_ERROR,
    PORTAPY_VALUE_BOOL,
    PORTAPY_VALUE_BYTES,
    PORTAPY_VALUE_CALLABLE,
    PORTAPY_VALUE_INT,
    PORTAPY_VALUE_NONE,
    PORTAPY_VALUE_OBJECT,
    PORTAPY_VALUE_STRING,
    _append_data_value,
    _append_value,
    _bind_global,
    _byte_data,
    _clear_runtime_error,
    _fail,
    _global_name,
    _global_runtime,
    _global_value,
    _last_status,
    _runtime_is_valid,
    _set_data_byte,
    _set_status,
    _value_data_size,
    _value_data_start,
    _value_i64,
    _value_is_valid,
    _value_kind,
    _value_refs,
    _portapy_runtime_create_impl as _base_runtime_create,
    _portapy_runtime_destroy_impl as _base_runtime_destroy,
    _portapy_value_release_impl as _base_value_release,
)
from .native_api_host import (
    _find_host_attr,
    _host_attr_value,
)
from .native_api_host_calls import _dispatch_host_call


_bridge_namespaces: list[dict[str, object]] = [{}]
_bridge_machines: list[VirtualMachine | None] = [None]


def _ensure_bridge_slot(runtime: int) -> None:
    while len(_bridge_namespaces) <= runtime:
        _bridge_namespaces.append({})
        _bridge_machines.append(None)


def _decode_utf8(start: int, size: int) -> str:
    result = ""
    index = 0
    while index < size:
        first = _byte_data[start + index]
        if first < 128:
            result += chr(first)
            index += 1
            continue
        if first < 224:
            needed = 1
            codepoint = first - 192
        elif first < 240:
            needed = 2
            codepoint = first - 224
        else:
            needed = 3
            codepoint = first - 240
        offset = 1
        while offset <= needed:
            codepoint = codepoint * 64 + _byte_data[start + index + offset] - 128
            offset += 1
        result += chr(codepoint)
        index += needed + 1
    return result


def _encode_utf8(value: str) -> list[int]:
    result: list[int] = []
    for character in value:
        codepoint = ord(character)
        if codepoint < 128:
            result.append(codepoint)
        elif codepoint < 2048:
            result.append(192 + codepoint // 64)
            result.append(128 + codepoint % 64)
        elif codepoint < 65536:
            result.append(224 + codepoint // 4096)
            result.append(128 + (codepoint // 64) % 64)
            result.append(128 + codepoint % 64)
        else:
            result.append(240 + codepoint // 262144)
            result.append(128 + (codepoint // 4096) % 64)
            result.append(128 + (codepoint // 64) % 64)
            result.append(128 + codepoint % 64)
    return result


class _HostObjectProxy:
    def __init__(self, runtime: int, host_id: int) -> None:
        self._runtime = runtime
        self._host_id = host_id

    def __getattr__(self, name: str) -> object:
        slot = _find_host_attr(self._runtime, self._host_id, name)
        if slot == 0:
            raise AttributeError(name)
        return _native_to_python(self._runtime, _host_attr_value[slot])


class _HostCallableProxy:
    def __init__(self, runtime: int, callable_id: int) -> None:
        self._runtime = runtime
        self._callable_id = callable_id

    def __call__(self, *args: object, **kwargs: object) -> object:
        if kwargs:
            raise TypeError("native host callables currently accept positional arguments")
        handles: list[int] = []
        for argument in args:
            handle = _python_to_native(self._runtime, argument)
            if handle == 0:
                raise TypeError("host callable argument cannot be represented by the native ABI")
            handles.append(handle)
        dispatched = _dispatch_host_call(
            self._runtime,
            self._callable_id,
            handles,
            0,
        )
        if dispatched[2] != PORTAPY_OK:
            raise RuntimeError("native host callable failed")
        result = _native_to_python(self._runtime, dispatched[0])
        _base_value_release(self._runtime, dispatched[0])
        return result


def _native_to_python(runtime: int, value: int) -> object:
    if not _value_is_valid(runtime, value):
        raise RuntimeError("invalid native value handle")
    kind = _value_kind[value]
    if kind == PORTAPY_VALUE_NONE:
        return None
    if kind == PORTAPY_VALUE_BOOL:
        return _value_i64[value] != 0
    if kind == PORTAPY_VALUE_INT:
        return _value_i64[value]
    if kind == PORTAPY_VALUE_STRING:
        return _decode_utf8(_value_data_start[value], _value_data_size[value])
    if kind == PORTAPY_VALUE_BYTES:
        data: list[int] = []
        index = 0
        while index < _value_data_size[value]:
            data.append(_byte_data[_value_data_start[value] + index])
            index += 1
        return bytes(data)
    if kind == PORTAPY_VALUE_CALLABLE:
        return _HostCallableProxy(runtime, _value_i64[value])
    if kind == PORTAPY_VALUE_OBJECT:
        return _HostObjectProxy(runtime, _value_i64[value])
    raise TypeError("native value kind is not bridged into the standalone VM")


def _python_to_native(runtime: int, value: object) -> int:
    if value is None:
        return _append_value(runtime, PORTAPY_VALUE_NONE, 0)
    if type(value) is bool:
        return _append_value(runtime, PORTAPY_VALUE_BOOL, 1 if value else 0)
    if type(value) is int:
        return _append_value(runtime, PORTAPY_VALUE_INT, value)
    if type(value) is str:
        encoded = _encode_utf8(value)
        handle = _append_data_value(runtime, PORTAPY_VALUE_STRING, len(encoded))
        index = 0
        while index < len(encoded):
            if _set_data_byte(runtime, handle, index, encoded[index]) != PORTAPY_OK:
                return 0
            index += 1
        return handle
    if type(value) is bytes:
        handle = _append_data_value(runtime, PORTAPY_VALUE_BYTES, len(value))
        index = 0
        while index < len(value):
            if _set_data_byte(runtime, handle, index, value[index]) != PORTAPY_OK:
                return 0
            index += 1
        return handle
    return 0


def _refresh_namespace(runtime: int) -> dict[str, object]:
    _ensure_bridge_slot(runtime)
    namespace = _bridge_namespaces[runtime]
    slot = 1
    while slot < len(_global_runtime):
        if _global_runtime[slot] == runtime and _global_name[slot] != "":
            handle = _global_value[slot]
            if _value_is_valid(runtime, handle):
                namespace[_global_name[slot]] = _native_to_python(runtime, handle)
        slot += 1
    return namespace


def _sync_scalar_globals(runtime: int, namespace: dict[str, object]) -> None:
    for name, value in namespace.items():
        if name.startswith("__"):
            continue
        handle = _python_to_native(runtime, value)
        if handle != 0:
            _bind_global(runtime, name, handle)


def _record_exception(runtime: int, status: int, error: BaseException) -> int:
    line = int(getattr(error, "lineno", 0) or 0)
    column = int(getattr(error, "offset", 0) or 0)
    return _fail(
        runtime,
        status,
        type(error).__name__,
        str(error),
        line,
        column,
    )


def _portapy_runtime_create_impl() -> int:
    runtime = _base_runtime_create()
    if runtime == 0:
        return 0
    _ensure_bridge_slot(runtime)
    _bridge_namespaces[runtime] = {
        "__name__": "__main__",
        "__package__": "",
        "__doc__": None,
    }
    _bridge_machines[runtime] = VirtualMachine()
    return runtime


def _portapy_runtime_destroy_impl(runtime: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _ensure_bridge_slot(runtime)
    _bridge_namespaces[runtime] = {}
    _bridge_machines[runtime] = None
    return _base_runtime_destroy(runtime)


def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    try:
        namespace = _refresh_namespace(runtime)
        machine = _bridge_machines[runtime]
        if machine is None:
            machine = VirtualMachine()
            _bridge_machines[runtime] = machine
        code = compile_source(source[0:source_size], "<portapy-native>", "exec")
        machine.run(code, namespace)
        _sync_scalar_globals(runtime, namespace)
        return _set_status(PORTAPY_OK)
    except BaseException as error:
        if _last_status[0] != PORTAPY_OK:
            return _last_status[0]
        status = PORTAPY_RUNTIME_ERROR
        if type(error).__name__ in {"SyntaxError", "PortableFrontendError"}:
            status = PORTAPY_COMPILE_ERROR
        return _record_exception(runtime, status, error)


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    try:
        namespace = _refresh_namespace(runtime)
        machine = _bridge_machines[runtime]
        if machine is None:
            machine = VirtualMachine()
            _bridge_machines[runtime] = machine
        code = compile_source(source[0:source_size], "<portapy-native-eval>", "eval")
        result = machine.run(code, namespace)
        handle = _python_to_native(runtime, result)
        if handle == 0:
            _fail(
                runtime,
                PORTAPY_TYPE_ERROR,
                "TypeError",
                "evaluation result cannot be represented by the native ABI bridge",
            )
            return 0
        _sync_scalar_globals(runtime, namespace)
        _set_status(PORTAPY_OK)
        return handle
    except BaseException as error:
        if _last_status[0] != PORTAPY_OK:
            return 0
        status = PORTAPY_RUNTIME_ERROR
        if type(error).__name__ in {"SyntaxError", "PortableFrontendError"}:
            status = PORTAPY_COMPILE_ERROR
        _record_exception(runtime, status, error)
        return 0
