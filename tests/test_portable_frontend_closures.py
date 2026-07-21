from __future__ import annotations

import builtins

from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import VirtualMachine


def run_source(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {"__builtins__": builtins.__dict__}
    VirtualMachine().run(compile_portable_source(source), namespace)
    return namespace


def test_returned_closure_reads_captured_value() -> None:
    namespace = run_source(
        "def make_adder(captured):\n"
        "    def add(value):\n"
        "        return value + captured\n"
        "    return add\n"
        "add_two = make_adder(2)\n"
        "answer = add_two(40)\n"
    )
    assert namespace["answer"] == 42


def test_nonlocal_state_persists_between_calls() -> None:
    namespace = run_source(
        "def make_counter(start):\n"
        "    value = start\n"
        "    def step(amount):\n"
        "        nonlocal value\n"
        "        value += amount\n"
        "        return value\n"
        "    return step\n"
        "counter = make_counter(40)\n"
        "first = counter(1)\n"
        "second = counter(1)\n"
    )
    assert namespace["first"] == 41
    assert namespace["second"] == 42


def test_closure_instances_keep_isolated_state() -> None:
    namespace = run_source(
        "def make_counter(start):\n"
        "    value = start\n"
        "    def step():\n"
        "        nonlocal value\n"
        "        value += 1\n"
        "        return value\n"
        "    return step\n"
        "left = make_counter(40)\n"
        "right = make_counter(9)\n"
        "left_value = left()\n"
        "right_value = right()\n"
        "answer = left()\n"
    )
    assert namespace["left_value"] == 41
    assert namespace["right_value"] == 10
    assert namespace["answer"] == 42


def test_nested_function_without_captures_is_bound() -> None:
    namespace = run_source(
        "def outer():\n"
        "    def answer():\n"
        "        return 42\n"
        "    return answer()\n"
        "value = outer()\n"
    )
    assert namespace["value"] == 42


def test_same_named_nested_functions_resolve_by_scope_position() -> None:
    namespace = run_source(
        "def left():\n"
        "    def value():\n"
        "        return 20\n"
        "    return value()\n"
        "def right():\n"
        "    def value():\n"
        "        return 22\n"
        "    return value()\n"
        "answer = left() + right()\n"
    )
    assert namespace["answer"] == 42
