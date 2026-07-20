"""High-level embeddable PortaPy environment API.

This is the stable object-oriented surface intended to be mirrored by native
binary imports. The hosted package uses :class:`portapy.reference_api.Runtime`
as its backend; an ``import_binary("portapy.dll")`` module can expose the same
``new()`` and ``Environment`` contract over native handles.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Mapping

from .reference_api import ErrorInfo, Runtime, Status


class PortaPyError(RuntimeError):
    """Base error raised by the high-level environment API."""


class EnvironmentClosedError(PortaPyError):
    """Raised when an operation targets a closed environment."""


class ExecutionError(PortaPyError):
    """Raised when PortaPy cannot compile or execute supplied source."""

    def __init__(self, error: ErrorInfo | None, *, operation: str) -> None:
        self.error = error
        self.operation = operation
        if error is None:
            message = f"PortaPy {operation} failed"
        else:
            message = f"{error.type_name}: {error.message}"
        super().__init__(message)


class BindingError(PortaPyError):
    """Raised when host bindings cannot be added safely."""


@dataclass(frozen=True)
class EnvironmentSnapshot:
    """A shallow snapshot of one environment's global-name bindings.

    Restoring the snapshot restores names and their referenced objects. It does
    not deep-copy or roll back mutations made inside arbitrary host objects,
    modules, services, or native handles.
    """

    _environment: "Environment"
    _bindings: tuple[tuple[str, object], ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self._bindings)

    def bindings(self) -> dict[str, object]:
        """Return a mutable copy of the captured global mapping."""
        return dict(self._bindings)

    def restore(self) -> "Environment":
        """Restore this snapshot into its originating environment."""
        self._environment._restore_bindings(dict(self._bindings))
        return self._environment


class Environment:
    """One isolated PortaPy execution environment."""

    def __init__(self, runtime: Runtime | None = None) -> None:
        self._runtime = runtime if runtime is not None else Runtime()
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise EnvironmentClosedError("PortaPy environment is closed")

    def _raise_status(self, status: Status, operation: str) -> None:
        if status is Status.OK:
            return
        if status is Status.CLOSED:
            self._closed = True
            raise EnvironmentClosedError("PortaPy environment is closed")
        raise ExecutionError(self._runtime.last_error(), operation=operation)

    def _bind(self, name: str, value: object, *, replace: bool) -> None:
        self._ensure_open()
        if not isinstance(name, str) or not name or not name.isidentifier():
            raise BindingError(f"invalid PortaPy binding name: {name!r}")
        status, exists = self._runtime.has_global(name)
        self._raise_status(status, "inspect globals")
        if exists and not replace:
            raise BindingError(f"PortaPy global already exists: {name}")
        self._raise_status(self._runtime.set_global(name, value), f"bind {name}")

    def add_module(
        self,
        module: ModuleType | object,
        *,
        name: str | None = None,
        replace: bool = False,
    ) -> "Environment":
        """Bind one host module under a module-style global name."""
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
    ) -> "Environment":
        """Bind host modules using each module's final dotted name component."""
        for module in modules:
            self.add_module(module, replace=replace)
        return self

    def expose(
        self,
        *sources: Mapping[str, object] | object,
        include_private: bool = False,
        replace: bool = False,
    ) -> "Environment":
        """Expose a mapping or object's members directly as PortaPy globals.

        This is the operation intended for Somnia's ``env`` module: a public
        member named ``game`` becomes directly available as ``game`` inside the
        executed script instead of requiring ``env.game``.
        """
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
    ) -> "Environment":
        """Compatibility alias for :meth:`expose`.

        ``expose`` is preferred because the operation exposes host bindings; it
        does not turn those values into language builtins.
        """
        return self.expose(
            source,
            include_private=include_private,
            replace=replace,
        )

    def set(self, name: str, value: object, *, replace: bool = True) -> "Environment":
        """Set one host value as a PortaPy global."""
        self._bind(name, value, replace=replace)
        return self

    def remove(self, name: str, *, missing_ok: bool = False) -> "Environment":
        """Remove one global binding."""
        self._ensure_open()
        status = self._runtime.delete_global(name)
        if status is Status.NOT_FOUND and missing_ok:
            self._runtime.clear_error()
            return self
        self._raise_status(status, f"remove {name}")
        return self

    def get(self, name: str) -> object:
        """Return one unboxed global value."""
        self._ensure_open()
        status, value = self._runtime.read_global(name)
        self._raise_status(status, f"read {name}")
        return value

    def execute(self, source: str, filename: str = "<portapy>") -> "Environment":
        """Compile and execute source in this environment."""
        self._ensure_open()
        self._raise_status(self._runtime.exec_utf8(source, filename), "execute")
        return self

    def evaluate(self, expression: str, filename: str = "<portapy-eval>") -> object:
        """Evaluate one expression and return its unboxed value."""
        self._ensure_open()
        status, handle = self._runtime.eval_utf8(expression, filename)
        self._raise_status(status, "evaluate")
        try:
            status, value = self._runtime.unbox(handle)
            self._raise_status(status, "unbox evaluation result")
            return value
        finally:
            if handle:
                self._runtime.release(handle)

    def snapshot(self) -> EnvironmentSnapshot:
        """Capture the environment's current shallow global bindings."""
        self._ensure_open()
        status, bindings = self._runtime.snapshot_globals()
        self._raise_status(status, "snapshot")
        return EnvironmentSnapshot(self, tuple(bindings.items()))

    def _restore_bindings(self, bindings: dict[str, object]) -> None:
        self._ensure_open()
        self._raise_status(self._runtime.restore_globals(bindings), "restore snapshot")

    def bindings(self) -> dict[str, object]:
        """Return a shallow copy of the current global namespace."""
        self._ensure_open()
        status, bindings = self._runtime.snapshot_globals()
        self._raise_status(status, "inspect globals")
        return bindings

    @property
    def last_error(self) -> ErrorInfo | None:
        return self._runtime.last_error()

    def close(self) -> None:
        if self._closed:
            return
        status = self._runtime.close()
        if status is not Status.OK and status is not Status.CLOSED:
            self._raise_status(status, "close")
        self._closed = True

    def __enter__(self) -> "Environment":
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.close()
        return False


def new(*, runtime: Runtime | None = None) -> Environment:
    """Create one isolated PortaPy environment."""
    return Environment(runtime)
