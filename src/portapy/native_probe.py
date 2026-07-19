"""First asmpython-compiled shared-library probe for PortaPy.

This deliberately exercises the vendored Python-built bytecode model. It is not
the final public ABI and must not be released as PortaPy 3.14.
"""
from core.bytecode import Instruction, Op


def portapy_abi_version() -> int:
    return 1


def portapy_opcode_probe() -> int:
    instruction = Instruction(Op.BINARY_ADD, 0)
    return instruction.op.value
