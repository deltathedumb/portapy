"""Replace generated environment execution with PortaPy's standalone full VM.

The host-call build owns target-specific host-object and callback state.  This
rewrite installs the full VM directly into that final generated module so host
attributes, pending callback frames, runtime handles, and value handles remain
shared with the established C ABI.
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path
import token
import tokenize


_SENTINEL = "# PORTAPY_STANDALONE_VM_ENVIRONMENT"
_RENAMED_DEFINITIONS = {
    "_portapy_exec_span_impl": "_incremental_portapy_exec_span_impl",
    "_portapy_eval_span_impl": "_incremental_portapy_eval_span_impl",
    "_portapy_runtime_destroy_impl": "_incremental_portapy_runtime_destroy_impl",
}


def _rename_definitions(source: str) -> tuple[str, dict[str, int]]:
    rewritten: list[tokenize.TokenInfo] = []
    counts = {name: 0 for name in _RENAMED_DEFINITIONS}
    after_def = False
    for item in tokenize.generate_tokens(StringIO(source).readline):
        if item.type == token.NAME and item.string == "def":
            after_def = True
            rewritten.append(item)
            continue
        if after_def and item.type == token.NAME:
            replacement = _RENAMED_DEFINITIONS.get(item.string)
            if replacement is not None:
                counts[item.string] += 1
                item = tokenize.TokenInfo(
                    item.type,
                    replacement,
                    item.start,
                    item.end,
                    item.line,
                )
            after_def = False
        elif after_def and item.type not in (tokenize.NL, tokenize.NEWLINE):
            after_def = False
        rewritten.append(item)
    return tokenize.untokenize(rewritten), counts


def _bridge_source(host_module: str) -> str:
    return f'''

{_SENTINEL}
from .core.frontend import compile_source as _full_compile_source
from .core.vm import VirtualMachine as _FullVirtualMachine
from .native_api import (
    PORTAPY_VALUE_NONE as _full_value_none,
    PORTAPY_VALUE_BOOL as _full_value_bool,
    PORTAPY_VALUE_INT as _full_value_int,
    PORTAPY_VALUE_STRING as _full_value_string,
    PORTAPY_VALUE_BYTES as _full_value_bytes,
    PORTAPY_VALUE_CALLABLE as _full_value_callable,
    PORTAPY_VALUE_OBJECT as _full_value_object,
    _append_data_value as _full_append_data_value,
    _append_value as _full_append_value,
    _byte_data as _full_byte_data,
    _global_name as _full_global_name,
    _global_runtime as _full_global_runtime,
    _global_value as _full_global_value,
    _last_status as _full_last_status,
    _portapy_runtime_create_impl as _full_base_runtime_create,
    _set_data_byte as _full_set_data_byte,
    _value_data_size as _full_value_data_size,
    _value_data_start as _full_value_data_start,
    _value_i64 as _full_value_i64,
)
from .{host_module} import (
    _host_find_host_attr as _full_find_host_attr,
    _host_attr_value as _full_host_attr_value,
)


_full_namespaces: list[dict[str, object]] = [{{}}]
_full_machines: list[_FullVirtualMachine | None] = [None]


def _full_ensure_slot(runtime: int) -> None:
    while len(_full_namespaces) <= runtime:
        _full_namespaces.append({{}})
        _full_machines.append(None)


def _full_decode_utf8(start: int, size: int) -> str:
    result = ""
    index = 0
    while index < size:
        first = _full_byte_data[start + index]
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
            codepoint = codepoint * 64 + _full_byte_data[start + index + offset] - 128
            offset += 1
        result += chr(codepoint)
        index += needed + 1
    return result


def _full_encode_utf8(value: str) -> list[int]:
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


class _FullHostObject:
    def __init__(self, runtime: int, host_id: int) -> None:
        self._runtime = runtime
        self._host_id = host_id

    def __getattr__(self, name: str) -> object:
        slot = _full_find_host_attr(self._runtime, self._host_id, name)
        if slot == 0:
            raise AttributeError(name)
        return _full_native_to_python(self._runtime, _full_host_attr_value[slot])


class _FullHostCallable:
    def __init__(self, runtime: int, callable_id: int) -> None:
        self._runtime = runtime
        self._callable_id = callable_id

    def __call__(self, *args: object, **kwargs: object) -> object:
        if kwargs:
            raise TypeError("native host callables accept positional arguments")
        handles: list[int] = []
        for argument in args:
            handle = _full_python_to_native(self._runtime, argument)
            if handle == 0:
                raise TypeError("host callback argument is not ABI-representable")
            handles.append(handle)
        dispatched = _dispatch_host_call(self._runtime, self._callable_id, handles, 0)
        if dispatched[2] != PORTAPY_OK:
            raise RuntimeError("native host callback failed")
        result_handle = dispatched[0]
        result = _full_native_to_python(self._runtime, result_handle)
        _portapy_value_release_impl(self._runtime, result_handle)
        return result


def _full_native_to_python(runtime: int, value: int) -> object:
    if not _value_is_valid(runtime, value):
        raise RuntimeError("invalid native value handle")
    kind = _value_kind[value]
    if kind == _full_value_none:
        return None
    if kind == _full_value_bool:
        return _full_value_i64[value] != 0
    if kind == _full_value_int:
        return _full_value_i64[value]
    if kind == _full_value_string:
        return _full_decode_utf8(
            _full_value_data_start[value],
            _full_value_data_size[value],
        )
    if kind == _full_value_bytes:
        data: list[int] = []
        index = 0
        while index < _full_value_data_size[value]:
            data.append(_full_byte_data[_full_value_data_start[value] + index])
            index += 1
        return bytes(data)
    if kind == _full_value_callable:
        return _FullHostCallable(runtime, _full_value_i64[value])
    if kind == _full_value_object:
        return _FullHostObject(runtime, _full_value_i64[value])
    raise TypeError("native value kind is not available in the full VM bridge")


def _full_python_to_native(runtime: int, value: object) -> int:
    if value is None:
        return _full_append_value(runtime, _full_value_none, 0)
    if type(value) is bool:
        return _full_append_value(runtime, _full_value_bool, 1 if value else 0)
    if type(value) is int:
        return _full_append_value(runtime, _full_value_int, value)
    if type(value) is str:
        encoded = _full_encode_utf8(value)
        handle = _full_append_data_value(runtime, _full_value_string, len(encoded))
        index = 0
        while index < len(encoded):
            if _full_set_data_byte(runtime, handle, index, encoded[index]) != PORTAPY_OK:
                return 0
            index += 1
        return handle
    if type(value) is bytes:
        handle = _full_append_data_value(runtime, _full_value_bytes, len(value))
        index = 0
        while index < len(value):
            if _full_set_data_byte(runtime, handle, index, value[index]) != PORTAPY_OK:
                return 0
            index += 1
        return handle
    return 0


def _full_refresh_namespace(runtime: int) -> dict[str, object]:
    _full_ensure_slot(runtime)
    namespace = _full_namespaces[runtime]
    slot = 1
    while slot < len(_full_global_runtime):
        if _full_global_runtime[slot] == runtime and _full_global_name[slot] != "":
            handle = _full_global_value[slot]
            if _value_is_valid(runtime, handle):
                namespace[_full_global_name[slot]] = _full_native_to_python(runtime, handle)
        slot += 1
    return namespace


def _full_sync_globals(runtime: int, namespace: dict[str, object]) -> None:
    for name, value in namespace.items():
        if name.startswith("__") or name == "True" or name == "False" or name == "None":
            continue
        handle = _full_python_to_native(runtime, value)
        if handle != 0:
            _bind_global(runtime, name, handle)


def _full_record_exception(runtime: int, status: int, error: BaseException) -> int:
    line = int(getattr(error, "lineno", 0) or 0)
    column = int(getattr(error, "offset", 0) or 0)
    return _fail(runtime, status, type(error).__name__, str(error), line, column)


def _portapy_runtime_create_impl() -> int:
    runtime = _full_base_runtime_create()
    if runtime == 0:
        return 0
    _full_ensure_slot(runtime)
    _full_namespaces[runtime] = {{
        "__name__": "__main__",
        "__package__": "",
        "__doc__": None,
    }}
    _full_machines[runtime] = _FullVirtualMachine()
    return runtime


def _portapy_runtime_destroy_impl(runtime: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _full_ensure_slot(runtime)
    _full_namespaces[runtime] = {{}}
    _full_machines[runtime] = None
    return _incremental_portapy_runtime_destroy_impl(runtime)


def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    if source_size < 0:
        return _fail(
            runtime,
            PORTAPY_INVALID_ARGUMENT,
            "ValueError",
            "source size cannot be negative",
        )
    try:
        namespace = _full_refresh_namespace(runtime)
        machine = _full_machines[runtime]
        if machine is None:
            machine = _FullVirtualMachine()
            _full_machines[runtime] = machine
        code = _full_compile_source(source[0:source_size], "<portapy-native>", "exec")
        machine.run(code, namespace)
        _full_sync_globals(runtime, namespace)
        return _set_status(PORTAPY_OK)
    except BaseException as error:
        if _full_last_status[0] != PORTAPY_OK:
            return _full_last_status[0]
        status = PORTAPY_RUNTIME_ERROR
        error_name = type(error).__name__
        if error_name == "SyntaxError" or error_name == "PortableFrontendError":
            status = PORTAPY_COMPILE_ERROR
        return _full_record_exception(runtime, status, error)


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    if source_size < 0:
        _fail(
            runtime,
            PORTAPY_INVALID_ARGUMENT,
            "ValueError",
            "source size cannot be negative",
        )
        return 0
    try:
        namespace = _full_refresh_namespace(runtime)
        machine = _full_machines[runtime]
        if machine is None:
            machine = _FullVirtualMachine()
            _full_machines[runtime] = machine
        code = _full_compile_source(
            source[0:source_size],
            "<portapy-native-eval>",
            "eval",
        )
        result = machine.run(code, namespace)
        handle = _full_python_to_native(runtime, result)
        if handle == 0:
            _fail(
                runtime,
                PORTAPY_TYPE_ERROR,
                "TypeError",
                "evaluation result is not ABI-representable",
            )
            return 0
        _full_sync_globals(runtime, namespace)
        _set_status(PORTAPY_OK)
        return handle
    except BaseException as error:
        if _full_last_status[0] != PORTAPY_OK:
            return 0
        status = PORTAPY_RUNTIME_ERROR
        error_name = type(error).__name__
        if error_name == "SyntaxError" or error_name == "PortableFrontendError":
            status = PORTAPY_COMPILE_ERROR
        _full_record_exception(runtime, status, error)
        return 0
'''


def rewrite_generated_full_vm_environment(path: Path, *, host_module: str) -> Path:
    if not host_module.isidentifier():
        raise ValueError(f"invalid generated host module: {host_module!r}")
    source = path.read_text(encoding="utf-8")
    if _SENTINEL in source:
        raise ValueError("generated environment already contains the standalone VM bridge")
    source, counts = _rename_definitions(source)
    unexpected = {name: count for name, count in counts.items() if count != 1}
    if unexpected:
        raise ValueError(f"unexpected generated public definition counts: {unexpected}")
    source = source.rstrip() + _bridge_source(host_module)
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_full_vm_environment"]
