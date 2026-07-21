"""Compile and execute source through PortaPy's standalone parser and full VM."""
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
