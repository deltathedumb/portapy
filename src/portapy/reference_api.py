"""Python-authored reference model for the PortaPy shared-library ABI.

Interpreter semantics live in ``portapy.core``, a source fork of pyinbin's
Python-written bytecode/frontend/VM/import core. No native-language interpreter
implementation is introduced here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import traceback

from .core.frontend import compile_source
from .core.vm import VirtualMachine


class Status(IntEnum):
    OK = 0
    INVALID_ARGUMENT = 1
    COMPILE_ERROR = 2
    RUNTIME_ERROR = 3
    TYPE_ERROR = 4
    NOT_FOUND = 5
    CLOSED = 6
    INVALID_HANDLE = 7


class ValueKind(IntEnum):
    NONE = 0
    BOOL = 1
    INT = 2
    FLOAT = 3
    STRING = 4
    BYTES = 5
    CALLABLE = 6
    OBJECT = 7


@dataclass(frozen=True)
class ErrorInfo:
    status: Status
    type_name: str
    message: str
    traceback_text: str


@dataclass
class _Slot:
    value: object
    refs: int = 1


class Runtime:
    def __init__(self) -> None:
        self._vm = VirtualMachine()
        self._globals: dict[str, object] = {}
        self._globals.update({"__name__": "__main__", "__package__": "", "__doc__": None})
        self._values: dict[int, _Slot] = {}
        self._next = 1
        self._eval_counter = 0
        self._last_error: ErrorInfo | None = None
        self._closed = False

    def _capture(self, status: Status, error: BaseException) -> Status:
        self._last_error = ErrorInfo(
            status,
            type(error).__name__,
            str(error),
            "".join(traceback.format_exception(error)),
        )
        return status

    def _ready(self) -> Status | None:
        if self._closed:
            self._last_error = ErrorInfo(
                Status.CLOSED,
                "RuntimeClosed",
                "PortaPy runtime has been destroyed",
                "",
            )
            return Status.CLOSED
        self._last_error = None
        return None

    def _store(self, value: object) -> int:
        handle = self._next
        self._next += 1
        self._values[handle] = _Slot(value)
        return handle

    def close(self) -> Status:
        if self._closed:
            return Status.CLOSED
        self._values.clear()
        self._globals.clear()
        self._last_error = None
        self._closed = True
        return Status.OK

    def last_error(self) -> ErrorInfo | None:
        return self._last_error

    def clear_error(self) -> None:
        self._last_error = None

    def exec_utf8(self, source: str, filename: str = "<portapy>") -> Status:
        blocked = self._ready()
        if blocked is not None:
            return blocked
        try:
            code = compile_source(source, filename)
        except BaseException as error:
            return self._capture(Status.COMPILE_ERROR, error)
        try:
            self._vm.run(code, self._globals)
        except BaseException as error:
            return self._capture(Status.RUNTIME_ERROR, error)
        return Status.OK

    def eval_utf8(
        self,
        expression: str,
        filename: str = "<portapy-eval>",
    ) -> tuple[Status, int]:
        blocked = self._ready()
        if blocked is not None:
            return blocked, 0
        self._eval_counter += 1
        name = f"__portapy_result_{self._eval_counter}"
        status = self.exec_utf8(f"{name} = ({expression})\n", filename)
        if status is not Status.OK:
            return status, 0
        return Status.OK, self._store(self._globals.pop(name))

    def get_global(self, name: str) -> tuple[Status, int]:
        blocked = self._ready()
        if blocked is not None:
            return blocked, 0
        if name not in self._globals:
            return self._capture(Status.NOT_FOUND, KeyError(name)), 0
        return Status.OK, self._store(self._globals[name])

    def call(
        self,
        callable_handle: int,
        args: list[int] | None = None,
    ) -> tuple[Status, int]:
        blocked = self._ready()
        if blocked is not None:
            return blocked, 0
        target = self._values.get(callable_handle)
        if target is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(callable_handle)), 0
        values: list[object] = []
        for handle in args or []:
            slot = self._values.get(handle)
            if slot is None:
                return self._capture(Status.INVALID_HANDLE, KeyError(handle)), 0
            values.append(slot.value)
        try:
            result = self._vm._call(target.value, values)
        except BaseException as error:
            return self._capture(Status.RUNTIME_ERROR, error), 0
        return Status.OK, self._store(result)

    def retain(self, handle: int) -> Status:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle))
        slot.refs += 1
        return Status.OK

    def release(self, handle: int) -> Status:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle))
        slot.refs -= 1
        if slot.refs <= 0:
            del self._values[handle]
        return Status.OK

    def box_none(self) -> tuple[Status, int]:
        return Status.OK, self._store(None)

    def box_bool(self, value: bool) -> tuple[Status, int]:
        return Status.OK, self._store(value)

    def box_int(self, value: int) -> tuple[Status, int]:
        return Status.OK, self._store(value)

    def box_float(self, value: float) -> tuple[Status, int]:
        return Status.OK, self._store(value)

    def box_utf8(self, value: str) -> tuple[Status, int]:
        return Status.OK, self._store(value)

    def box_bytes(self, value: bytes) -> tuple[Status, int]:
        return Status.OK, self._store(value)

    def value_kind(self, handle: int) -> tuple[Status, ValueKind]:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), ValueKind.OBJECT
        value = slot.value
        if value is None:
            kind = ValueKind.NONE
        elif type(value) is bool:
            kind = ValueKind.BOOL
        elif type(value) is int:
            kind = ValueKind.INT
        elif type(value) is float:
            kind = ValueKind.FLOAT
        elif type(value) is str:
            kind = ValueKind.STRING
        elif type(value) is bytes:
            kind = ValueKind.BYTES
        elif callable(value):
            kind = ValueKind.CALLABLE
        else:
            kind = ValueKind.OBJECT
        return Status.OK, kind

    def as_int(self, handle: int) -> tuple[Status, int]:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), 0
        if type(slot.value) is not int:
            return self._capture(Status.TYPE_ERROR, TypeError("value is not int")), 0
        return Status.OK, slot.value

    def as_float(self, handle: int) -> tuple[Status, float]:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), 0.0
        if type(slot.value) is not float:
            return self._capture(Status.TYPE_ERROR, TypeError("value is not float")), 0.0
        return Status.OK, slot.value

    def as_utf8(self, handle: int) -> tuple[Status, bytes]:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), b""
        if type(slot.value) is not str:
            return self._capture(Status.TYPE_ERROR, TypeError("value is not str")), b""
        return Status.OK, slot.value.encode("utf-8")
