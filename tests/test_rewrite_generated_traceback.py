from __future__ import annotations

import ast
from pathlib import Path

from tools.rewrite_generated_traceback import (
    _EXECUTION_BLOCK,
    _state_and_api,
    rewrite_generated_traceback,
)


def _trace_namespace() -> dict[str, object]:
    status = [3]

    def set_status(value: int) -> int:
        status[0] = value
        return value

    namespace: dict[str, object] = {
        "PORTAPY_OK": 0,
        "PORTAPY_INVALID_ARGUMENT": 1,
        "PORTAPY_NOT_FOUND": 5,
        "PORTAPY_INVALID_HANDLE": 7,
        "_function_definition_line": [0, 1, 3],
        "_function_body": ["", "return missing", "return inner()"],
        "_function_name": ["", "inner", "outer"],
        "_function_parameters": ["", "", ""],
        "_runtime_error_line": [0, 2],
        "_runtime_is_valid": lambda runtime: runtime in (1, 2),
        "_portapy_error_column_impl": lambda runtime: set_status(0) or 12,
        "_portapy_last_status_impl": lambda: status[0],
        "_set_status": set_status,
        "_trim": lambda source, start, end: [
            len(source[:end]) - len(source[:end].lstrip()),
            len(source[:end].rstrip()),
        ],
        "status": status,
    }
    exec(_state_and_api(), namespace)
    return namespace


def _text(namespace: dict[str, object], prefix: str, runtime: int, index: int) -> str:
    size = namespace[f"_portapy_traceback_{prefix}_size_impl"](runtime, index)
    byte = namespace[f"_portapy_traceback_{prefix}_byte_impl"]
    return bytes(byte(runtime, index, offset) for offset in range(size)).decode("utf-8")


def test_traceback_frames_are_returned_outermost_first() -> None:
    namespace = _trace_namespace()
    namespace["_portapy_traceback_add_function_impl"](1, 1)
    namespace["_portapy_traceback_add_function_impl"](1, 2)
    namespace["_portapy_traceback_add_impl"](1, 5, 1, "<module>", "result = outer()")

    assert namespace["_portapy_traceback_count_impl"](1) == 3
    assert [_text(namespace, "function", 1, index) for index in range(3)] == [
        "<module>",
        "outer",
        "inner",
    ]
    assert _text(namespace, "source", 1, 1) == "def outer():"
    assert _text(namespace, "source", 1, 2) == "return missing"


def test_traceback_capture_preserves_failure_status() -> None:
    namespace = _trace_namespace()
    namespace["status"][0] = 3

    assert namespace["_portapy_traceback_add_function_impl"](1, 1) == 0
    assert namespace["status"][0] == 3


def test_traceback_reset_is_per_runtime() -> None:
    namespace = _trace_namespace()
    add = namespace["_portapy_traceback_add_impl"]
    add(1, 1, 1, "one", "source one")
    add(2, 2, 1, "two", "source two")

    assert namespace["_portapy_traceback_reset_impl"](1) == 0
    assert namespace["_portapy_traceback_count_impl"](1) == 0
    assert namespace["_portapy_traceback_count_impl"](2) == 1


def test_invalid_runtime_is_rejected() -> None:
    namespace = _trace_namespace()

    assert namespace["_portapy_traceback_count_impl"](99) == 0
    assert namespace["status"][0] == 7


def test_traceback_rewrite_instruments_function_unwind(tmp_path: Path) -> None:
    path = tmp_path / "generated.py"
    path.write_text(
        "_MAX_CALL_DEPTH = 128\n"
        "def invoke():\n"
        + _EXECUTION_BLOCK
        + "\n",
        encoding="utf-8",
    )

    rewrite_generated_traceback(path)
    rewritten = path.read_text(encoding="utf-8")
    ast.parse(rewritten)

    assert "_portapy_traceback_add_function_impl(runtime, slot)" in rewritten
    assert "_portapy_traceback_count_impl" in rewritten
