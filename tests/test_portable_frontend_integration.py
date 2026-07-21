from __future__ import annotations

import builtins

from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import VirtualMachine


def test_standalone_frontend_cross_feature_module_executes() -> None:
    namespace: dict[str, object] = {"__builtins__": builtins.__dict__}
    source = (
        "class Box:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "def make_offset(offset):\n"
        "    def apply(value):\n"
        "        return value + offset\n"
        "    return apply\n"
        "offset = make_offset(2)\n"
        "values = [offset(value) for value in [18, 20] if value >= 20]\n"
        "try:\n"
        "    boxed = Box(values[0])\n"
        "except ValueError:\n"
        "    result = 0\n"
        "else:\n"
        "    match boxed.value:\n"
        "        case 22:\n"
        "            result = boxed.value + 20\n"
        "        case _:\n"
        "            result = 0\n"
        "answer = result\n"
    )
    VirtualMachine().run(compile_portable_source(source), namespace)
    assert namespace["answer"] == 42
