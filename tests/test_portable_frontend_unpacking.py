from __future__ import annotations

import builtins

from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import VirtualMachine


def run_source(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {"__builtins__": builtins.__dict__}
    VirtualMachine().run(compile_portable_source(source), namespace)
    return namespace


def test_starred_calls_and_variadic_functions_execute() -> None:
    namespace = run_source(
        "def combine(first, *rest, **named):\n"
        "    return first + rest[0] + named['last']\n"
        "parts = (20, 1)\n"
        "options = {'last': 21}\n"
        "answer = combine(*parts, **options)\n"
    )
    assert namespace["answer"] == 42


def test_explicit_keywords_and_mapping_unpack_merge() -> None:
    namespace = run_source(
        "def combine(first, second=0, **named):\n"
        "    return first + second + named['last']\n"
        "options = {'last': 2}\n"
        "answer = combine(20, second=20, **options)\n"
    )
    assert namespace["answer"] == 42


def test_container_unpacking_executes_in_source_order() -> None:
    namespace = run_source(
        "base = [1, 2]\n"
        "values = [0, *base, 3]\n"
        "pair = (20, *[22])\n"
        "unique = {0, *base, 3}\n"
        "mapping = {**{'left': 20}, 'right': 22}\n"
        "answer = pair[0] + pair[1]\n"
    )
    assert namespace["values"] == [0, 1, 2, 3]
    assert namespace["pair"] == (20, 22)
    assert namespace["unique"] == {0, 1, 2, 3}
    assert namespace["mapping"] == {"left": 20, "right": 22}
    assert namespace["answer"] == 42
