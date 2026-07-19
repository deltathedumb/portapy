from __future__ import annotations

import builtins

import pytest

from portapy.core.portable_frontend import (
    PortableFrontendError,
    compile_portable_source,
)
from portapy.core.vm import VirtualMachine


def run_source(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {"__builtins__": builtins.__dict__}
    VirtualMachine().run(compile_portable_source(source), namespace)
    return namespace


def test_assignment_and_arithmetic_execute_without_host_ast() -> None:
    namespace = run_source("answer = 40 + 2\n")
    assert namespace["answer"] == 42


def test_function_definition_call_and_return_execute() -> None:
    namespace = run_source(
        "def add(a, b):\n"
        "    return a + b\n"
        "answer = add(20, 22)\n"
    )
    assert namespace["answer"] == 42


def test_literals_keep_bool_none_float_and_string_values() -> None:
    namespace = run_source(
        "truth = True\n"
        "nothing = None\n"
        "fraction = 1.5\n"
        "text = 'portapy'\n"
    )
    assert namespace["truth"] is True
    assert namespace["nothing"] is None
    assert namespace["fraction"] == 1.5
    assert namespace["text"] == "portapy"


def test_unsupported_statement_fails_precisely() -> None:
    with pytest.raises(PortableFrontendError, match="If"):
        compile_portable_source("if True:\n    value = 1\n")


def test_portable_frontend_source_has_no_host_ast_import() -> None:
    import inspect
    import portapy.core.portable_frontend as frontend

    source = inspect.getsource(frontend)
    assert "import ast" not in source
    assert "from ast" not in source
