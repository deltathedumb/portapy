"""Compile and execute one program through PortaPy's full Python core.

This is a release-readiness probe, not a replacement API. Passing it proves the
vendored frontend and VM can be compiled together into a native shared library.
"""
from __future__ import annotations

from .core.frontend import compile_source
from .core.vm import VirtualMachine


def portapy_abi_version() -> int:
    return 1


def portapy_full_core_probe() -> int:
    namespace: dict[str, object] = {}
    code = compile_source("answer = 40 + 2\n", "<native-full-core-probe>")
    machine = VirtualMachine()
    machine.run(code, namespace)
    return namespace.get("answer", -1)
