from __future__ import annotations

import builtins

from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import VirtualMachine


def run_source(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {"__builtins__": builtins.__dict__}
    VirtualMachine().run(compile_portable_source(source), namespace)
    return namespace


def test_try_except_else_and_finally_execute() -> None:
    namespace = run_source(
        "normal = 1\n"
        "try:\n"
        "    normal += 1\n"
        "except ValueError:\n"
        "    normal = 0\n"
        "else:\n"
        "    normal += 20\n"
        "finally:\n"
        "    normal += 20\n"
        "handled = False\n"
        "finalized = False\n"
        "try:\n"
        "    raise ValueError('portable')\n"
        "except (TypeError, ValueError) as error:\n"
        "    handled = str(error) == 'portable'\n"
        "finally:\n"
        "    finalized = True\n"
    )
    assert namespace["normal"] == 42
    assert namespace["handled"] is True
    assert namespace["finalized"] is True


def test_generator_yields_and_resumes() -> None:
    namespace = run_source(
        "def answers():\n"
        "    yield 20\n"
        "    yield 22\n"
        "values = answers()\n"
        "first = next(values)\n"
        "second = next(values)\n"
        "answer = first + second\n"
    )
    assert namespace["first"] == 20
    assert namespace["second"] == 22
    assert namespace["answer"] == 42
