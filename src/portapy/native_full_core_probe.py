"""Execute one bytecode program through PortaPy's complete native VM.

Source parsing is validated separately because the hosted frontend currently
uses CPython's ``ast.parse``. Passing this probe proves that PortaPy's complete
CodeObject/Frame/VirtualMachine execution core works as a standalone library.
"""
from __future__ import annotations

from .core.bytecode import CodeObject, Instruction, Op
from .core.vm import VirtualMachine


def portapy_abi_version() -> int:
    return 1


def portapy_full_core_probe() -> int:
    namespace: dict[str, object] = {}
    code = CodeObject(
        name="<native-full-core-probe>",
        instructions=[
            Instruction(Op.LOAD_CONST, 0),
            Instruction(Op.STORE_NAME, 0),
        ],
        constants=[42],
        names=["answer"],
    )
    machine = VirtualMachine()
    machine.run(code, namespace)
    return namespace.get("answer", -1)
