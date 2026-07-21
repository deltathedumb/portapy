"""Reusable Python-built PortaPy interpreter core."""
from .bytecode import CodeObject, Instruction, Op
from .portable_frontend import (
    PortableFrontendError,
    compile_portable_source as compile_source,
)
from .vm import VMError, VirtualMachine

# Backward-compatible name retained for callers that imported the old frontend
# exception from ``portapy.core``.
PyinbinUnsupportedError = PortableFrontendError

__all__ = [
    "CodeObject", "Instruction", "Op", "PortableFrontendError",
    "PyinbinUnsupportedError", "VMError", "VirtualMachine", "compile_source",
]
