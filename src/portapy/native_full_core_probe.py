"""Compile and execute source through PortaPy's standalone parser and full VM."""
from __future__ import annotations

from .core.frontend import compile_source
from .core.vm import VirtualMachine


_PROBE_SOURCE = """def outer():
    value = 40
    def inner():
        return value + 2
    return inner()

class Box:
    def __init__(self, value):
        self.value = value

box = Box(outer())
answer = box.value
"""


def portapy_abi_version() -> int:
    return 1


def portapy_full_core_probe() -> int:
    namespace: dict[str, object] = {}
    code = compile_source(_PROBE_SOURCE, "<native-full-core-probe>")
    machine = VirtualMachine()
    machine.run(code, namespace)
    return namespace.get("answer", -1)
