from __future__ import annotations

import builtins

from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import VirtualMachine


def run_source(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {"__builtins__": builtins.__dict__}
    VirtualMachine().run(compile_portable_source(source), namespace)
    return namespace


def test_tuple_unpacking_for_loop_executes() -> None:
    namespace = run_source(
        "total = 0\n"
        "for left, right in [(1, 2), (20, 19)]:\n"
        "    total += left + right\n"
        "answer = total\n"
    )
    assert namespace["answer"] == 42


def test_nested_unpacking_for_loop_executes() -> None:
    namespace = run_source(
        "answer = 0\n"
        "for index, (left, right) in [(1, (20, 21))]:\n"
        "    answer = index + left + right\n"
    )
    assert namespace["answer"] == 42
