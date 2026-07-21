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
    value = int('40')
    if not isinstance(value, int):
        return -100
    def inner():
        return value + demo.offset
    return inner()

class Box:
    def __init__(self, value):
        self.value = value

try:
    int('not-an-integer')
except ValueError:
    box = Box(outer())
    answer = box.value

def crash():
    return 1 / 0

crash()
"""


def portapy_abi_version() -> int:
    return 1


def portapy_full_core_probe() -> int:
    namespace: dict[str, object] = {}
    namespace["__pyinbin_import__"] = _probe_import
    code = compile_source(_PROBE_SOURCE, "<native-full-core-probe>")
    machine = VirtualMachine()
    try:
        machine.run(code, namespace)
    except Exception as error:
        trace = machine._synthetic_tracebacks.get(id(error))
        found = False
        while trace is not None:
            if trace.tb_frame.f_code.co_name == "crash":
                found = True
            trace = trace.tb_next
        if found:
            return namespace.get("answer", -1)
        return -2
    return -3
