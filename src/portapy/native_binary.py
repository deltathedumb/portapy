"""High-level Python adapter for PortaPy's native DLL/SO artifacts.

``import_binary(path)`` returns a module-like facade with the same ``new()``
entry point as the hosted package. Python objects and callables are registered
onto the native host bridge automatically for ``add_modules()`` and ``expose()``.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Callable, Mapping

from .environment import (
    BindingError,
    EnvironmentClosedError,
    ExecutionError,
    PortaPyError,
)
from .reference_api import ErrorInfo, Status, ValueKind


_U64 = ctypes.c_uint64
_I64 = ctypes.c_int64
_SIZE = ctypes.c_size_t
_STATUS = ctypes.c_int
_BYTE = ctypes.c_uint8


class _Config(ctypes.Structure):
    _fields_ = [
        ("struct_size", _SIZE),
        ("abi_version", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("host_context", ctypes.c_void_p),
    ]


class _ErrorInfo(ctypes.Structure):
    _fields_ = [
        ("struct_size", _SIZE),
        ("status", _STATUS),
        ("reserved", ctypes.c_uint32),
        ("line", _SIZE),
        ("column", _SIZE),
        ("type_size", _SIZE),
        ("message_size", _SIZE),
    ]


_HOST_HANDLER = ctypes.CFUNCTYPE(
    _STATUS,
    ctypes.c_void_p,
    _U64,
    _U64,
    ctypes.POINTER(_U64),
    _SIZE,
    ctypes.POINTER(_U64),
)


@dataclass(frozen=True)
class NativeHostReference:
    """Fallback representation for an unregistered native host object ID."""

    host_id: int


@dataclass(frozen=True)
class NativeCallableReference:
    """Fallback representation for a callable not owned by the Python adapter."""

    callable_id: int | None = None


@dataclass(frozen=True)
class NativeEnvironmentSnapshot:
    """Shallow snapshot of one native environment's global bindings."""

    _environment: "NativeEnvironment"
    _bindings: tuple[tuple[str, object], ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self._bindings)

    @property
    def var(self) -> Mapping[str, object]:
        return MappingProxyType(dict(self._bindings))

    def __getitem__(self, name: str) -> object:
        return self.var[name]

    def get(self, name: str, default: object = None) -> object:
        return self.var.get(name, default)

    def bindings(self) -> dict[str, object]:
        return dict(self._bindings)

    def restore(self) -> "NativeEnvironment":
        self._environment._restore_bindings(dict(self._bindings))
        return self._environment


class _NativeLibrary:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        self.handle = ctypes.CDLL(str(self.path))
        self._bind()
        status = int(self.handle.portapy_library_initialize())
        if status != int(Status.OK):
            raise PortaPyError(f"PortaPy native library initialization failed: {status}")
        abi = int(self.handle.portapy_abi_version())
        if abi != 1:
            raise PortaPyError(f"unsupported PortaPy ABI version: {abi}")

    def _function(
        self,
        name: str,
        argtypes: list[object],
        restype: object = _STATUS,
    ) -> object:
        function = getattr(self.handle, name)
        function.argtypes = argtypes
        function.restype = restype
        return function

    def _bind(self) -> None:
        self._function("portapy_library_initialize", [])
        self._function("portapy_abi_version", [], ctypes.c_uint32)
        self._function(
            "portapy_runtime_create",
            [ctypes.POINTER(_Config), ctypes.POINTER(_U64)],
        )
        self._function("portapy_runtime_destroy", [_U64])
        self._function(
            "portapy_exec_utf8",
            [_U64, ctypes.c_void_p, _SIZE, ctypes.c_void_p, _SIZE],
        )
        self._function(
            "portapy_eval_utf8",
            [_U64, ctypes.c_void_p, _SIZE, ctypes.c_void_p, _SIZE, ctypes.POINTER(_U64)],
        )
        self._function(
            "portapy_get_global_utf8",
            [_U64, ctypes.c_void_p, _SIZE, ctypes.POINTER(_U64)],
        )
        self._function(
            "portapy_set_global_utf8",
            [_U64, ctypes.c_void_p, _SIZE, _U64],
        )
        self._function(
            "portapy_delete_global_utf8",
            [_U64, ctypes.c_void_p, _SIZE],
        )
        self._function("portapy_global_count", [_U64, ctypes.POINTER(_SIZE)])
        self._function(
            "portapy_global_name_copy_utf8",
            [_U64, _SIZE, ctypes.POINTER(_BYTE), _SIZE, ctypes.POINTER(_SIZE)],
        )
        self._function("portapy_value_from_none", [_U64, ctypes.POINTER(_U64)])
        self._function(
            "portapy_value_from_bool",
            [_U64, ctypes.c_int, ctypes.POINTER(_U64)],
        )
        self._function(
            "portapy_value_from_i64",
            [_U64, _I64, ctypes.POINTER(_U64)],
        )
        self._function(
            "portapy_value_from_f64",
            [_U64, ctypes.c_double, ctypes.POINTER(_U64)],
        )
        self._function(
            "portapy_value_from_utf8",
            [_U64, ctypes.c_void_p, _SIZE, ctypes.POINTER(_U64)],
        )
        self._function(
            "portapy_value_from_bytes",
            [_U64, ctypes.c_void_p, _SIZE, ctypes.POINTER(_U64)],
        )
        self._function(
            "portapy_value_from_host_object",
            [_U64, _U64, ctypes.POINTER(_U64)],
        )
        self._function(
            "portapy_value_from_host_callable",
            [_U64, _U64, ctypes.POINTER(_U64)],
        )
        self._function(
            "portapy_value_get_kind",
            [_U64, _U64, ctypes.POINTER(_STATUS)],
        )
        self._function(
            "portapy_value_as_bool",
            [_U64, _U64, ctypes.POINTER(ctypes.c_int)],
        )
        self._function(
            "portapy_value_as_i64",
            [_U64, _U64, ctypes.POINTER(_I64)],
        )
        self._function(
            "portapy_value_as_f64",
            [_U64, _U64, ctypes.POINTER(ctypes.c_double)],
        )
        self._function(
            "portapy_value_get_host_id",
            [_U64, _U64, ctypes.POINTER(_U64)],
        )
        self._function(
            "portapy_value_get_host_callable_id",
            [_U64, _U64, ctypes.POINTER(_U64)],
        )
        self._function(
            "portapy_value_get_size",
            [_U64, _U64, ctypes.POINTER(_SIZE)],
        )
        self._function(
            "portapy_value_copy_data",
            [_U64, _U64, ctypes.POINTER(_BYTE), _SIZE, ctypes.POINTER(_SIZE)],
        )
        self._function("portapy_value_retain", [_U64, _U64])
        self._function("portapy_value_release", [_U64, _U64])
        self._function(
            "portapy_host_set_attr_utf8",
            [_U64, _U64, ctypes.c_void_p, _SIZE, _U64],
        )
        self._function(
            "portapy_host_set_call_handler",
            [_U64, _HOST_HANDLER, ctypes.c_void_p],
        )
        self._function(
            "portapy_error_get_info",
            [_U64, ctypes.POINTER(_ErrorInfo)],
        )
        self._function(
            "portapy_error_copy_type_utf8",
            [_U64, ctypes.POINTER(_BYTE), _SIZE, ctypes.POINTER(_SIZE)],
        )
        self._function(
            "portapy_error_copy_message_utf8",
            [_U64, ctypes.POINTER(_BYTE), _SIZE, ctypes.POINTER(_SIZE)],
        )
        self._function("portapy_error_clear", [_U64])


class NativeEnvironment:
    """One isolated native PortaPy runtime with automatic Python host binding."""

    def __init__(self, library: _NativeLibrary) -> None:
        self._library = library
        self._api = library.handle
        self._runtime = _U64(0)
        self._closed = False
        self._objects: dict[int, object] = {}
        self._object_ids: dict[int, int] = {}
        self._callables: dict[int, Callable[..., object]] = {}
        self._callable_ids: dict[int, int] = {}
        self._next_host_id = 1
        self._next_callable_id = 1
        config = _Config(ctypes.sizeof(_Config), 1, 0, None)
        self._check(
            int(self._api.portapy_runtime_create(ctypes.byref(config), ctypes.byref(self._runtime))),
            "create runtime",
        )
        self._callback = _HOST_HANDLER(self._dispatch)
        self._check(
            int(self._api.portapy_host_set_call_handler(self._runtime, self._callback, None)),
            "install host callback",
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise EnvironmentClosedError("PortaPy environment is closed")

    @staticmethod
    def _bytes(text: str) -> bytes:
        try:
            return text.encode("ascii")
        except UnicodeEncodeError as error:
            raise BindingError("native PortaPy identifiers must be ASCII") from error

    @staticmethod
    def _buffer(data: bytes) -> tuple[object, ctypes.c_void_p]:
        if not data:
            return None, ctypes.c_void_p()
        storage = ctypes.create_string_buffer(data, len(data))
        return storage, ctypes.cast(storage, ctypes.c_void_p)

    def _error_text(self, function: object) -> str:
        required = _SIZE(0)
        status = int(function(self._runtime, None, 0, ctypes.byref(required)))
        if required.value == 0:
            return ""
        if status not in (int(Status.OK), int(Status.INVALID_ARGUMENT)):
            return ""
        buffer = (_BYTE * required.value)()
        status = int(function(self._runtime, buffer, required.value, ctypes.byref(required)))
        if status != int(Status.OK):
            return ""
        return bytes(buffer).decode("utf-8", errors="replace")

    def _last_error(self) -> ErrorInfo | None:
        info = _ErrorInfo()
        info.struct_size = ctypes.sizeof(_ErrorInfo)
        status = int(self._api.portapy_error_get_info(self._runtime, ctypes.byref(info)))
        if status != int(Status.OK) or info.status == int(Status.OK):
            return None
        try:
            error_status = Status(info.status)
        except ValueError:
            error_status = Status.RUNTIME_ERROR
        type_name = self._error_text(self._api.portapy_error_copy_type_utf8)
        message = self._error_text(self._api.portapy_error_copy_message_utf8)
        location = ""
        if info.line or info.column:
            location = f"line {info.line}, column {info.column}"
        return ErrorInfo(error_status, type_name, message, location)

    @property
    def last_error(self) -> ErrorInfo | None:
        return self._last_error()

    def _check(
        self,
        status: int,
        operation: str,
        *,
        allow_not_found: bool = False,
    ) -> bool:
        if status == int(Status.OK):
            return True
        if allow_not_found and status == int(Status.NOT_FOUND):
            self._api.portapy_error_clear(self._runtime)
            return False
        if status == int(Status.CLOSED):
            self._closed = True
            raise EnvironmentClosedError("PortaPy environment is closed")
        raise ExecutionError(self._last_error(), operation=operation)

    def _new_value(self, function: object, *arguments: object) -> int:
        handle = _U64(0)
        status = int(function(self._runtime, *arguments, ctypes.byref(handle)))
        self._check(status, "box host value")
        return int(handle.value)

    def _register_callable(self, value: Callable[..., object]) -> int:
        key = id(value)
        existing = self._callable_ids.get(key)
        if existing is not None:
            return existing
        callable_id = self._next_callable_id
        self._next_callable_id += 1
        self._callable_ids[key] = callable_id
        self._callables[callable_id] = value
        return callable_id

    def _members(self, value: object) -> tuple[tuple[str, object], ...]:
        if isinstance(value, Mapping):
            source = value.items()
        else:
            try:
                source = vars(value).items()
            except TypeError:
                source = ()
        members: list[tuple[str, object]] = []
        for name, member in source:
            if (
                isinstance(name, str)
                and not name.startswith("_")
                and name.isidentifier()
                and name.isascii()
            ):
                members.append((name, member))
        return tuple(members)

    def _register_object(self, value: object) -> int:
        key = id(value)
        existing = self._object_ids.get(key)
        if existing is not None:
            return existing
        host_id = self._next_host_id
        self._next_host_id += 1
        self._object_ids[key] = host_id
        self._objects[host_id] = value
        owner = self._new_value(
            self._api.portapy_value_from_host_object,
            _U64(host_id),
        )
        try:
            for name, member in self._members(value):
                child = self._box(member)
                encoded = self._bytes(name)
                storage, pointer = self._buffer(encoded)
                try:
                    self._check(
                        int(
                            self._api.portapy_host_set_attr_utf8(
                                self._runtime,
                                _U64(owner),
                                pointer,
                                len(encoded),
                                _U64(child),
                            )
                        ),
                        f"register attribute {name}",
                    )
                finally:
                    _ = storage
                    self._api.portapy_value_release(self._runtime, _U64(child))
        finally:
            self._api.portapy_value_release(self._runtime, _U64(owner))
        return host_id

    def _box(self, value: object) -> int:
        if value is None:
            return self._new_value(self._api.portapy_value_from_none)
        if isinstance(value, bool):
            return self._new_value(self._api.portapy_value_from_bool, int(value))
        if isinstance(value, int):
            if value < -(2**63) or value >= 2**63:
                raise BindingError("native PortaPy integers must fit signed 64-bit")
            return self._new_value(self._api.portapy_value_from_i64, _I64(value))
        if isinstance(value, float):
            return self._new_value(self._api.portapy_value_from_f64, value)
        if isinstance(value, str):
            data = value.encode("utf-8")
            storage, pointer = self._buffer(data)
            try:
                return self._new_value(self._api.portapy_value_from_utf8, pointer, len(data))
            finally:
                _ = storage
        if isinstance(value, (bytes, bytearray, memoryview)):
            data = bytes(value)
            storage, pointer = self._buffer(data)
            try:
                return self._new_value(self._api.portapy_value_from_bytes, pointer, len(data))
            finally:
                _ = storage
        if callable(value):
            callable_id = self._register_callable(value)
            return self._new_value(
                self._api.portapy_value_from_host_callable,
                _U64(callable_id),
            )
        host_id = self._register_object(value)
        return self._new_value(
            self._api.portapy_value_from_host_object,
            _U64(host_id),
        )

    def _copy_value_data(self, handle: int) -> bytes:
        required = _SIZE(0)
        self._check(
            int(self._api.portapy_value_get_size(self._runtime, _U64(handle), ctypes.byref(required))),
            "inspect value size",
        )
        if required.value == 0:
            return b""
        buffer = (_BYTE * required.value)()
        self._check(
            int(
                self._api.portapy_value_copy_data(
                    self._runtime,
                    _U64(handle),
                    buffer,
                    required.value,
                    ctypes.byref(required),
                )
            ),
            "copy value data",
        )
        return bytes(buffer)

    def _unbox(self, handle: int) -> object:
        kind = _STATUS(0)
        self._check(
            int(self._api.portapy_value_get_kind(self._runtime, _U64(handle), ctypes.byref(kind))),
            "inspect value kind",
        )
        value_kind = ValueKind(kind.value)
        if value_kind is ValueKind.NONE:
            return None
        if value_kind is ValueKind.BOOL:
            result = ctypes.c_int(0)
            self._check(
                int(self._api.portapy_value_as_bool(self._runtime, _U64(handle), ctypes.byref(result))),
                "unbox bool",
            )
            return bool(result.value)
        if value_kind is ValueKind.INT:
            result = _I64(0)
            self._check(
                int(self._api.portapy_value_as_i64(self._runtime, _U64(handle), ctypes.byref(result))),
                "unbox int",
            )
            return int(result.value)
        if value_kind is ValueKind.FLOAT:
            result = ctypes.c_double(0)
            self._check(
                int(self._api.portapy_value_as_f64(self._runtime, _U64(handle), ctypes.byref(result))),
                "unbox float",
            )
            return float(result.value)
        if value_kind is ValueKind.STRING:
            return self._copy_value_data(handle).decode("utf-8")
        if value_kind is ValueKind.BYTES:
            return self._copy_value_data(handle)
        if value_kind is ValueKind.OBJECT:
            host_id = _U64(0)
            self._check(
                int(
                    self._api.portapy_value_get_host_id(
                        self._runtime,
                        _U64(handle),
                        ctypes.byref(host_id),
                    )
                ),
                "recover host object",
            )
            return self._objects.get(int(host_id.value), NativeHostReference(int(host_id.value)))
        if value_kind is ValueKind.CALLABLE:
            callable_id = _U64(0)
            status = int(
                self._api.portapy_value_get_host_callable_id(
                    self._runtime,
                    _U64(handle),
                    ctypes.byref(callable_id),
                )
            )
            if status == int(Status.OK):
                return self._callables.get(
                    int(callable_id.value),
                    NativeCallableReference(int(callable_id.value)),
                )
            self._api.portapy_error_clear(self._runtime)
            return NativeCallableReference()
        raise BindingError(f"unsupported native value kind: {value_kind!r}")

    def _dispatch(
        self,
        context: object,
        runtime: int,
        callable_id: int,
        arguments: object,
        argument_count: int,
        out_result: object,
    ) -> int:
        del context
        if self._closed or int(runtime) != int(self._runtime.value):
            return int(Status.INVALID_HANDLE)
        function = self._callables.get(int(callable_id))
        if function is None:
            return int(Status.NOT_FOUND)
        try:
            values = [self._unbox(int(arguments[index])) for index in range(argument_count)]
            result = self._box(function(*values))
            out_result[0] = _U64(result)
            return int(Status.OK)
        except BaseException:
            out_result[0] = _U64(0)
            return int(Status.RUNTIME_ERROR)

    def _has_global(self, name: str) -> bool:
        encoded = self._bytes(name)
        storage, pointer = self._buffer(encoded)
        handle = _U64(0)
        try:
            status = int(
                self._api.portapy_get_global_utf8(
                    self._runtime,
                    pointer,
                    len(encoded),
                    ctypes.byref(handle),
                )
            )
            if not self._check(status, f"inspect global {name}", allow_not_found=True):
                return False
            self._api.portapy_value_release(self._runtime, handle)
            return True
        finally:
            _ = storage

    def _bind(self, name: str, value: object, *, replace: bool) -> None:
        self._ensure_open()
        if not name or not name.isidentifier() or not name.isascii():
            raise BindingError(f"invalid native PortaPy binding name: {name!r}")
        if self._has_global(name) and not replace:
            raise BindingError(f"PortaPy global already exists: {name}")
        handle = self._box(value)
        encoded = self._bytes(name)
        storage, pointer = self._buffer(encoded)
        try:
            self._check(
                int(
                    self._api.portapy_set_global_utf8(
                        self._runtime,
                        pointer,
                        len(encoded),
                        _U64(handle),
                    )
                ),
                f"bind {name}",
            )
        finally:
            _ = storage
            self._api.portapy_value_release(self._runtime, _U64(handle))

    def add_module(
        self,
        module: ModuleType | object,
        *,
        name: str | None = None,
        replace: bool = False,
    ) -> "NativeEnvironment":
        module_name = name
        if module_name is None:
            declared = getattr(module, "__name__", None)
            if not isinstance(declared, str) or not declared:
                raise BindingError("module object has no usable __name__")
            module_name = declared.rsplit(".", 1)[-1]
        self._bind(module_name, module, replace=replace)
        return self

    def add_modules(
        self,
        *modules: ModuleType | object,
        replace: bool = False,
    ) -> "NativeEnvironment":
        for module in modules:
            self.add_module(module, replace=replace)
        return self

    def expose(
        self,
        *sources: Mapping[str, object] | object,
        include_private: bool = False,
        replace: bool = False,
    ) -> "NativeEnvironment":
        for source in sources:
            if isinstance(source, Mapping):
                entries = source.items()
            else:
                try:
                    entries = vars(source).items()
                except TypeError as error:
                    raise BindingError(
                        f"cannot expose members from {type(source).__name__}"
                    ) from error
            for name, value in entries:
                if not isinstance(name, str):
                    raise BindingError("exposed binding names must be strings")
                if not include_private and name.startswith("_"):
                    continue
                self._bind(name, value, replace=replace)
        return self

    def add_builtin(
        self,
        source: Mapping[str, object] | object,
        *,
        include_private: bool = False,
        replace: bool = False,
    ) -> "NativeEnvironment":
        return self.expose(
            source,
            include_private=include_private,
            replace=replace,
        )

    def set(self, name: str, value: object, *, replace: bool = True) -> "NativeEnvironment":
        self._bind(name, value, replace=replace)
        return self

    def get(self, name: str) -> object:
        self._ensure_open()
        encoded = self._bytes(name)
        storage, pointer = self._buffer(encoded)
        handle = _U64(0)
        try:
            self._check(
                int(
                    self._api.portapy_get_global_utf8(
                        self._runtime,
                        pointer,
                        len(encoded),
                        ctypes.byref(handle),
                    )
                ),
                f"read {name}",
            )
            return self._unbox(int(handle.value))
        finally:
            _ = storage
            if handle.value:
                self._api.portapy_value_release(self._runtime, handle)

    def remove(self, name: str, *, missing_ok: bool = False) -> "NativeEnvironment":
        self._ensure_open()
        encoded = self._bytes(name)
        storage, pointer = self._buffer(encoded)
        try:
            status = int(
                self._api.portapy_delete_global_utf8(
                    self._runtime,
                    pointer,
                    len(encoded),
                )
            )
            if missing_ok and status == int(Status.NOT_FOUND):
                self._api.portapy_error_clear(self._runtime)
                return self
            self._check(status, f"remove {name}")
            return self
        finally:
            _ = storage

    def execute(self, source: str, filename: str = "<portapy>") -> "NativeEnvironment":
        self._ensure_open()
        source_data = source.encode("utf-8")
        filename_data = filename.encode("utf-8")
        source_storage, source_pointer = self._buffer(source_data)
        filename_storage, filename_pointer = self._buffer(filename_data)
        try:
            self._check(
                int(
                    self._api.portapy_exec_utf8(
                        self._runtime,
                        source_pointer,
                        len(source_data),
                        filename_pointer,
                        len(filename_data),
                    )
                ),
                "execute",
            )
            return self
        finally:
            _ = source_storage, filename_storage

    def evaluate(self, expression: str, filename: str = "<portapy-eval>") -> object:
        self._ensure_open()
        source_data = expression.encode("utf-8")
        filename_data = filename.encode("utf-8")
        source_storage, source_pointer = self._buffer(source_data)
        filename_storage, filename_pointer = self._buffer(filename_data)
        handle = _U64(0)
        try:
            self._check(
                int(
                    self._api.portapy_eval_utf8(
                        self._runtime,
                        source_pointer,
                        len(source_data),
                        filename_pointer,
                        len(filename_data),
                        ctypes.byref(handle),
                    )
                ),
                "evaluate",
            )
            return self._unbox(int(handle.value))
        finally:
            _ = source_storage, filename_storage
            if handle.value:
                self._api.portapy_value_release(self._runtime, handle)

    def _global_names(self) -> tuple[str, ...]:
        count = _SIZE(0)
        self._check(
            int(self._api.portapy_global_count(self._runtime, ctypes.byref(count))),
            "enumerate globals",
        )
        names: list[str] = []
        for index in range(count.value):
            required = _SIZE(0)
            status = int(
                self._api.portapy_global_name_copy_utf8(
                    self._runtime,
                    index,
                    None,
                    0,
                    ctypes.byref(required),
                )
            )
            if required.value == 0:
                self._check(status, "inspect global name")
                continue
            if status not in (int(Status.OK), int(Status.INVALID_ARGUMENT)):
                self._check(status, "inspect global name")
            buffer = (_BYTE * required.value)()
            self._check(
                int(
                    self._api.portapy_global_name_copy_utf8(
                        self._runtime,
                        index,
                        buffer,
                        required.value,
                        ctypes.byref(required),
                    )
                ),
                "copy global name",
            )
            names.append(bytes(buffer).decode("ascii"))
        return tuple(names)

    def bindings(self) -> dict[str, object]:
        self._ensure_open()
        return {name: self.get(name) for name in self._global_names()}

    def snapshot(self) -> NativeEnvironmentSnapshot:
        return NativeEnvironmentSnapshot(self, tuple(self.bindings().items()))

    def _restore_bindings(self, bindings: dict[str, object]) -> None:
        self._ensure_open()
        for name in self._global_names():
            if name not in bindings:
                self.remove(name)
        for name, value in bindings.items():
            self.set(name, value, replace=True)

    def close(self) -> None:
        if self._closed:
            return
        status = int(self._api.portapy_runtime_destroy(self._runtime))
        if status not in (int(Status.OK), int(Status.CLOSED)):
            self._check(status, "close")
        self._closed = True
        self._objects.clear()
        self._object_ids.clear()
        self._callables.clear()
        self._callable_ids.clear()

    def __enter__(self) -> "NativeEnvironment":
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.close()
        return False


class NativePortaPyModule:
    """Module-like facade returned by :func:`import_binary`."""

    Environment = NativeEnvironment
    EnvironmentSnapshot = NativeEnvironmentSnapshot
    Snapshot = NativeEnvironmentSnapshot
    PortaPyError = PortaPyError
    ExecutionError = ExecutionError
    BindingError = BindingError
    EnvironmentClosedError = EnvironmentClosedError

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self._library = _NativeLibrary(self.path)

    def new(self) -> NativeEnvironment:
        return NativeEnvironment(self._library)


def import_binary(path: str | Path) -> NativePortaPyModule:
    """Load a PortaPy native artifact and return its high-level module facade."""

    return NativePortaPyModule(path)


def load_native(path: str | Path) -> NativePortaPyModule:
    """Readable alias for :func:`import_binary`."""

    return import_binary(path)


__all__ = [
    "NativeCallableReference",
    "NativeEnvironment",
    "NativeEnvironmentSnapshot",
    "NativeHostReference",
    "NativePortaPyModule",
    "import_binary",
    "load_native",
]
