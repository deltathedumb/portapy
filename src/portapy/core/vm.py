"""Runtime entrypoint for PortaPy's Python-authored virtual machine.

The full implementation remains in :mod:`portapy.core.vm_impl` so native probe
workflows can normalize that source in an isolated checkout. This wrapper owns
hosted runtime setup that must happen before every top-level execution.
"""
from __future__ import annotations

from .bytecode import CodeObject
from .vm_impl import *  # noqa: F401,F403
from .vm_impl import VirtualMachine as _VirtualMachine


class VirtualMachine(_VirtualMachine):
    """VM entrypoint that mirrors Python's automatic builtin injection."""

    def run(self, code: CodeObject, globals_: dict[str, object] | None = None) -> object:
        namespace = globals_ if globals_ is not None else {}
        self._seed_builtins(namespace)
        return super().run(code, namespace)


__all__ = [name for name in globals() if not name.startswith("_")]
