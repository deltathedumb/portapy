from __future__ import annotations

import builtins

from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import VirtualMachine


def run_source(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {"__builtins__": builtins.__dict__}
    VirtualMachine().run(compile_portable_source(source), namespace)
    return namespace


def test_filtered_and_nested_list_comprehensions_execute() -> None:
    namespace = run_source(
        "filtered = [value * value for value in [1, 2, 3, 4] if value > 2]\n"
        "nested = [left + right for left in [10, 20] for right in [1, 2]]\n"
    )
    assert namespace["filtered"] == [9, 16]
    assert namespace["nested"] == [11, 12, 21, 22]


def test_unpacking_comprehension_targets_execute() -> None:
    namespace = run_source(
        "values = [left + right for left, right in [(1, 2), (20, 22)]]\n"
        "answer = values[1]\n"
    )
    assert namespace["values"] == [3, 42]
    assert namespace["answer"] == 42


def test_dictionary_comprehension_executes() -> None:
    namespace = run_source(
        "mapping = {str(value): value * value for value in [1, 2, 3] if value > 1}\n"
        "answer = mapping['2'] + mapping['3'] + 29\n"
    )
    assert namespace["mapping"] == {"2": 4, "3": 9}
    assert namespace["answer"] == 42
