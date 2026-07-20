"""High-level, Python-shaped PortaPy embedding API.

This is the stable interface intended to be exposed by binary-module loaders:

    portapy = import_binary("portapy.dll")
    environment = portapy.new()
    environment.add_modules(math)
    environment.expose(somnia.env)
    environment.execute("answer = seed + 1")
    answer = environment.snapshot().var["answer"]

The low-level opaque-handle ABI remains available underneath this facade.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

from .reference_api import ErrorInfo, Runtime, Status


class PortaPyError(RuntimeError):
    """Base exception raised by the high-level embedding API."""

    def __init__(self, message: str, info: ErrorInfo | None = None) -> None:
        super().__init__(message)
        self.info = info


class PortaPyExecutionError(PortaPyError):
    """Raised when compiling or executing code fails."""


@dataclass(frozen=True)
class Snapshot:
    """Detached shallow view of an environment's global namespace."""

    var: Mapping[str, object]

    def __getitem__(self, name: str) -> object:
        return self.var[name]

    def get(self, name: str, default: object = None) -> object:
        return self.var.get(name, default)


class Environment:
    """One isolated PortaPy runtime and its injected host namespace."""

    def __init__(self, runtime: Runtime | None = None) -> None:
        self._runtime = runtime or Runtime()
        self._closed = False

    @property
    def runtime(self) -> Runtime:
        """Return the backing runtime for advanced embedding operations."""
        return self._runtime

    def _raise_status(self, status: Status, operation: str) -> None:
        if status is Status.OK:
            return
        info = self._runtime.last_error()
        if info is None:
            raise PortaPyError(f"{operation} failed with status {status.name}")
        detail = f"{info.type_name}: {info.message}" if info.message else info.type_name
        raise PortaPyExecutionError(f"{operation} failed: {detail}", info)

    def _set(self, name: str, value: object) -> None:
        status = self._runtime.set_global(name, value)
        self._raise_status(status, f"injecting {name!r}")

    def add_module(self, module: object, name: str | None = None) -> "Environment":
        """Add one module-like object under a qualified global name."""
        module_name = name
        if module_name is None:
            module_name = getattr(module, "__name__", "")
            if module_name:
                module_name = module_name.rsplit(".", 1)[-1]
        if not module_name:
            raise ValueError("module name is required for objects without __name__")
        self._set(module_name, module)
        return self

    def add_modules(self, *modules: object, **named_modules: object) -> "Environment":
        """Add modules while preserving ``module.member`` access."""
        for module in modules:
            self.add_module(module)
        for name, module in named_modules.items():
            self.add_module(module, name)
        return self

    def expose(
        self,
        source: object,
        names: Iterable[str] | None = None,
        *,
        include_private: bool = False,
    ) -> "Environment":
        """Flatten selected names from a module, object, or mapping into globals.

        ``expose(somnia.env)`` is the intended replacement for the less precise
        name ``add_builtin``. It makes values such as ``game`` directly available
        to executed code without requiring ``env.game``.
        """
        if isinstance(source, Mapping):
            values = dict(source)
        else:
            values = vars(source)

        selected = list(names) if names is not None else list(values)
        for name in selected:
            if not include_private and name.startswith("_"):
                continue
            if name not in values:
                raise KeyError(name)
            self._set(name, values[name])
        return self

    def execute(self, source: str, filename: str = "<portapy>") -> "Environment":
        """Compile and execute source inside this environment."""
        status = self._runtime.exec_utf8(source, filename)
        self._raise_status(status, "execution")
        return self

    def evaluate(self, expression: str, filename: str = "<portapy-eval>") -> object:
        """Evaluate one expression and return its host-side value."""
        status, handle = self._runtime.eval_utf8(expression, filename)
        self._raise_status(status, "evaluation")
        try:
            status, value = self._runtime.unbox(handle)
            self._raise_status(status, "value conversion")
            return value
        finally:
            if handle:
                self._runtime.release(handle)

    def snapshot(self, *, include_private: bool = False) -> Snapshot:
        """Capture the current global namespace without retaining a live view."""
        status, values = self._runtime.snapshot_globals(include_private)
        self._raise_status(status, "snapshot")
        return Snapshot(MappingProxyType(values))

    def close(self) -> None:
        if self._closed:
            return
        status = self._runtime.close()
        if status is not Status.OK and status is not Status.CLOSED:
            self._raise_status(status, "closing environment")
        self._closed = True

    def __enter__(self) -> "Environment":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def new(runtime: Runtime | None = None) -> Environment:
    """Create a new isolated PortaPy environment."""
    return Environment(runtime)
