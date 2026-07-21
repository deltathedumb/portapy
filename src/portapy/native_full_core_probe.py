"""Execute every release-blocking subsystem through the standalone full core."""
from __future__ import annotations

from .core.frontend import compile_source
from .core.vm import VirtualMachine


class _ProbeModule:
    def __init__(self) -> None:
        self.value = 42


def _probe_import(name: str) -> object:
    return _ProbeModule()


def _probe_source() -> str:
    return (
        "def outer(base):\n"
        "    def inner(value):\n"
        "        return base + value\n"
        "    return inner\n"
        "class Box:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "    def add(self, other):\n"
        "        return self.value + other\n"
        "fn = outer(base=19)\n"
        "box = Box(value=fn(value=23))\n"
        "import probe\n"
        "def fail():\n"
        "    return 1 // 0\n"
        "try:\n"
        "    fail()\n"
        "except Exception as exc:\n"
        "    traced = exc.__traceback__ is not None\n"
        "answer = box.add(other=0) + probe.value - 42 if traced else -1\n"
    )


def portapy_abi_version() -> int:
    return 1


def portapy_full_core_parse_probe() -> int:
    code = compile_source(_probe_source(), "<native-full-core-parse-probe>")
    return len(code.instructions)


def portapy_full_core_probe() -> int:
    namespace: dict[str, object] = {}
    namespace["__pyinbin_import__"] = _probe_import
    namespace["Exception"] = Exception
    code = compile_source(_probe_source(), "<native-full-core-probe>")
    machine = VirtualMachine()
    machine.run(code, namespace)
    return namespace.get("answer", -1)
