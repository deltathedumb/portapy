from __future__ import annotations

import builtins

from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import VirtualMachine


def run_source(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {"__builtins__": builtins.__dict__}
    VirtualMachine().run(compile_portable_source(source), namespace)
    return namespace


def test_class_body_observes_prior_module_bindings() -> None:
    namespace = run_source(
        "factor = 21\n"
        "class Scaled:\n"
        "    value = factor * 2\n"
        "answer = Scaled.value\n"
    )
    assert namespace["answer"] == 42


def test_statements_between_definitions_execute_in_order() -> None:
    namespace = run_source(
        "state = 20\n"
        "def read_state():\n"
        "    return state\n"
        "state = state + 22\n"
        "answer = read_state()\n"
    )
    assert namespace["answer"] == 42


def test_decorator_definition_precedes_decorated_function() -> None:
    namespace = run_source(
        "def identity(function):\n"
        "    return function\n"
        "@identity\n"
        "def answer():\n"
        "    return 42\n"
        "value = answer()\n"
    )
    assert namespace["value"] == 42
