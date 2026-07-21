"""Runtime entrypoint for PortaPy's Python-authored virtual machine.

The implementation lives in :mod:`portapy.core.vm_impl`; this module owns the
small amount of top-level runtime setup shared by hosted and native callers.
"""
from __future__ import annotations

from .bytecode import CodeObject
from .vm_impl import VMError, VirtualMachine as _VirtualMachine


class VirtualMachine(_VirtualMachine):
    """VM entrypoint that mirrors Python's automatic builtin injection."""

    def run(self, code: CodeObject, globals_: dict[str, object] | None = None) -> object:
        namespace = globals_ if globals_ is not None else {}
        self._seed_builtins(namespace)
        return super().run(code, namespace)


__all__ = ["VMError", "VirtualMachine"]
