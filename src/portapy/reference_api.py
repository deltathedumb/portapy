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
    TUPLE = 8


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

    def has_global(self, name: str) -> tuple[Status, bool]:
        blocked = self._ready()
        if blocked is not None:
            return blocked, False
        if not isinstance(name, str) or not name:
            return self._capture(
                Status.INVALID_ARGUMENT,
                ValueError("global name must be a non-empty string"),
            ), False
        return Status.OK, name in self._globals

    def set_global(self, name: str, value: object) -> Status:
        blocked = self._ready()
        if blocked is not None:
            return blocked
        if not isinstance(name, str) or not name:
            return self._capture(
                Status.INVALID_ARGUMENT,
                ValueError("global name must be a non-empty string"),
            )
        self._globals[name] = value
        return Status.OK

    def get_global(self, name: str) -> tuple[Status, int]:
        blocked = self._ready()
        if blocked is not None:
            return blocked, 0
        if name not in self._globals:
            return self._capture(Status.NOT_FOUND, KeyError(name)), 0
        return Status.OK, self._store(self._globals[name])

    def exec(self, source: str, filename: str = "<portapy>") -> Status:
        blocked = self._ready()
        if blocked is not None:
            return blocked
        try:
            code = compile_source(source, filename, "exec")
            self._vm.run_code(code, self._globals)
        except SyntaxError as error:
            return self._capture(Status.COMPILE_ERROR, error)
        except BaseException as error:
            return self._capture(Status.RUNTIME_ERROR, error)
        return Status.OK

    def eval(self, source: str, filename: str = "<portapy>") -> tuple[Status, int]:
        blocked = self._ready()
        if blocked is not None:
            return blocked, 0
        self._eval_counter += 1
        result_name = f"__portapy_eval_result_{self._eval_counter}"
        try:
            code = compile_source(f"{result_name} = ({source})", filename, "exec")
            self._vm.run_code(code, self._globals)
            result = self._globals.pop(result_name)
        except SyntaxError as error:
            self._globals.pop(result_name, None)
            return self._capture(Status.COMPILE_ERROR, error), 0
        except BaseException as error:
            self._globals.pop(result_name, None)
            return self._capture(Status.RUNTIME_ERROR, error), 0
        return Status.OK, self._store(result)

    def kind(self, handle: int) -> tuple[Status, ValueKind]:
        blocked = self._ready()
        if blocked is not None:
            return blocked, ValueKind.OBJECT
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), ValueKind.OBJECT
        value = slot.value
        if value is None:
            kind = ValueKind.NONE
        elif isinstance(value, bool):
            kind = ValueKind.BOOL
        elif isinstance(value, int):
            kind = ValueKind.INT
        elif isinstance(value, float):
            kind = ValueKind.FLOAT
        elif isinstance(value, str):
            kind = ValueKind.STRING
        elif isinstance(value, bytes):
            kind = ValueKind.BYTES
        elif isinstance(value, tuple):
            kind = ValueKind.TUPLE
        elif callable(value):
            kind = ValueKind.CALLABLE
        else:
            kind = ValueKind.OBJECT
        return Status.OK, kind

    def value(self, handle: int) -> tuple[Status, object]:
        blocked = self._ready()
        if blocked is not None:
            return blocked, None
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), None
        return Status.OK, slot.value

    def retain(self, handle: int) -> Status:
        blocked = self._ready()
        if blocked is not None:
            return blocked
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle))
        slot.refs += 1
        return Status.OK

    def release(self, handle: int) -> Status:
        blocked = self._ready()
        if blocked is not None:
            return blocked
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle))
        slot.refs -= 1
        if slot.refs <= 0:
            del self._values[handle]
        return Status.OK
