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


def test_comparisons_boolean_values_and_conditional_expression() -> None:
    namespace = run_source(
        "between = 1 < 2 < 3\n"
        "fallback = 0 or 7\n"
        "continued = 5 and 9\n"
        "choice = 42 if between else 0\n"
        "negative = -choice\n"
        "inverted = not between\n"
    )
    assert namespace["between"] is True
    assert namespace["fallback"] == 7
    assert namespace["continued"] == 9
    assert namespace["choice"] == 42
    assert namespace["negative"] == -42
    assert namespace["inverted"] is False


def test_if_else_and_while_execute() -> None:
    namespace = run_source(
        "total = 0\n"
        "number = 1\n"
        "while number <= 6:\n"
        "    total = total + number\n"
        "    number = number + 1\n"
        "if total == 21:\n"
        "    answer = 42\n"
        "else:\n"
        "    answer = 0\n"
    )
    assert namespace["total"] == 21
    assert namespace["answer"] == 42


def test_unsupported_statement_fails_precisely() -> None:
    with pytest.raises(PortableFrontendError, match="ListLit"):
        compile_portable_source("value = [1, 2, 3]\n")


def test_portable_frontend_source_has_no_host_ast_import() -> None:
    import inspect
    import portapy.core.portable_frontend as frontend

    import_lines = [
        line.strip()
        for line in inspect.getsource(frontend).splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    assert "import ast" not in import_lines
    assert not any(line.startswith("from ast ") for line in import_lines)
