from __future__ import annotations

from portapy.core.frontend import compile_source
from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import VirtualMachine


def test_vm_run_injects_builtin_names() -> None:
    namespace: dict[str, object] = {}
    code = compile_portable_source(
        "values = list(range(3))\n"
        "answer = len(values) + 39\n"
    )
    VirtualMachine().run(code, namespace)
    assert namespace["values"] == [0, 1, 2]
    assert namespace["answer"] == 42


def test_core_frontend_eval_mode_returns_expression_value() -> None:
    namespace: dict[str, object] = {}
    result = VirtualMachine().run(
        compile_source("sum(range(7)) * 2", mode="eval"),
        namespace,
    )
    assert result == 42
    assert "__portapy_compiled_result" not in namespace


def test_core_frontend_single_expression_is_interactive() -> None:
    code = compile_source("40 + 2", mode="single")
    assert code.interactive is True
    assert VirtualMachine().run(code, {}) == 42


def test_core_frontend_single_statement_executes() -> None:
    namespace: dict[str, object] = {}
    code = compile_source("answer = 40 + 2\n", mode="single")
    assert code.interactive is True
    VirtualMachine().run(code, namespace)
    assert namespace["answer"] == 42
