"""Compile and execute closures and classes through the standalone full core."""
from __future__ import annotations

from .core.frontend import compile_source
from .core.vm import VirtualMachine


def portapy_abi_version() -> int:
    return 1


def portapy_full_core_probe() -> int:
    source = (
        "def outer(base):\n"
        "    def inner(value):\n"
        "        return base + value\n"
        "    return inner\n"
        "class Box:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "    def get(self):\n"
        "        return self.value\n"
        "fn = outer(19)\n"
        "box = Box(fn(23))\n"
        "answer = box.get()\n"
    )
    namespace: dict[str, object] = {}
    code = compile_source(source, "<native-full-core-probe>")
    machine = VirtualMachine()
    machine.run(code, namespace)
    return namespace.get("answer", -1)
