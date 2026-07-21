"""Compile and execute source through PortaPy's standalone parser and full VM."""
from __future__ import annotations

from .core.frontend import compile_source
from .core.vm import VirtualMachine


class _ProbeModule:
    def __init__(self) -> None:
        self.offset = 2


def _probe_import(name: str) -> object:
    return _ProbeModule()


_PROBE_SOURCE = """import demo

def outer():
    value = 40
    def inner():
        return value + demo.offset
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
    namespace["__pyinbin_import__"] = _probe_import
    code = compile_source(_PROBE_SOURCE, "<native-full-core-probe>")
    machine = VirtualMachine()
    machine.run(code, namespace)
    return namespace.get("answer", -1)
