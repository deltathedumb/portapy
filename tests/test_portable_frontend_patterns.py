from __future__ import annotations

import builtins

from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import VirtualMachine


def run_source(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {"__builtins__": builtins.__dict__}
    VirtualMachine().run(compile_portable_source(source), namespace)
    return namespace


def test_value_or_capture_and_guard_patterns_execute() -> None:
    namespace = run_source(
        "subject = 2\n"
        "match subject:\n"
        "    case 1:\n"
        "        answer = 0\n"
        "    case 2 | 3 if subject > 1:\n"
        "        answer = 42\n"
        "    case _:\n"
        "        answer = -1\n"
    )
    assert namespace["answer"] == 42


def test_sequence_and_mapping_patterns_bind_values() -> None:
    namespace = run_source(
        "sequence = [20, 1, 2, 22]\n"
        "match sequence:\n"
        "    case [first, *middle, last]:\n"
        "        sequence_answer = first + last\n"
        "mapping = {'answer': 42}\n"
        "match mapping:\n"
        "    case {'answer': captured}:\n"
        "        mapping_answer = captured\n"
    )
    assert namespace["middle"] == [1, 2]
    assert namespace["sequence_answer"] == 42
    assert namespace["mapping_answer"] == 42


def test_keyword_class_pattern_uses_vm_attributes() -> None:
    namespace = run_source(
        "class Point:\n"
        "    def __init__(self, x, y):\n"
        "        self.x = x\n"
        "        self.y = y\n"
        "point = Point(20, 22)\n"
        "match point:\n"
        "    case Point(x=left, y=right):\n"
        "        answer = left + right\n"
    )
    assert namespace["answer"] == 42
