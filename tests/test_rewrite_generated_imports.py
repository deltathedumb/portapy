from __future__ import annotations

import ast
from pathlib import Path

from tools.rewrite_generated_imports import _helpers, rewrite_generated_imports


def _namespace() -> dict[str, object]:
    ok = 0
    compile_error = 2
    not_found = 5
    invalid_handle = 7
    runtime = 1
    values = {
        10: {"answer": 11, "nested": 12},
        12: {"value": 13},
    }
    globals_by_name = {"helpers": 10}
    failures: list[tuple[int, str, str, int, int]] = []
    delegated: list[str] = []

    def skip_space(source: str, end: int, position: int) -> int:
        while position < end and source[position].isspace():
            position += 1
        return position

    def parse_identifier(source: str, end: int, position: int) -> list[int]:
        position = skip_space(source, end, position)
        if position >= end or (not source[position].isalpha() and source[position] != "_"):
            return [position, position, compile_error]
        start = position
        position += 1
        while position < end and (source[position].isalnum() or source[position] == "_"):
            position += 1
        return [start, position, ok]

    def trim(source: str, start: int, end: int) -> list[int]:
        while start < end and source[start].isspace():
            start += 1
        while end > start and source[end - 1].isspace():
            end -= 1
        return [start, end]

    def fail(
        runtime_handle: int,
        status: int,
        type_name: str,
        message: str,
        line: int = 0,
        column: int = 0,
    ) -> int:
        assert runtime_handle == runtime
        failures.append((status, type_name, message, line, column))
        return status

    def set_status(status: int) -> int:
        return status

    def bind_global(runtime_handle: int, name: str, value: int) -> int:
        assert runtime_handle == runtime
        globals_by_name[name] = value
        return ok

    def retain_global(runtime_handle: int, name: str, position: int) -> list[int]:
        assert runtime_handle == runtime
        value = globals_by_name.get(name)
        if value is None:
            return [0, position, not_found]
        return [value, position, ok]

    def release(runtime_handle: int, value: int) -> None:
        assert runtime_handle == runtime
        assert value in values or value in globals_by_name.values()

    def host_attr(runtime_handle: int, owner: int, name: str, name_size: int) -> int:
        assert runtime_handle == runtime
        assert len(name) == name_size
        return int(values.get(owner, {}).get(name, 0))

    def resolve_path(runtime_handle: int, source: str, start: int, end: int) -> list[int]:
        assert runtime_handle == runtime
        pieces = [part.strip() for part in source[start:end].split(".")]
        current = globals_by_name.get(pieces[0], 0)
        for piece in pieces[1:]:
            current = int(values.get(current, {}).get(piece, 0))
        return [current, end, ok if current else not_found]

    def downstream(runtime_handle: int, source: str, size: int) -> int:
        assert runtime_handle == runtime
        delegated.append(source[:size])
        return ok

    namespace: dict[str, object] = {
        "PORTAPY_OK": ok,
        "PORTAPY_COMPILE_ERROR": compile_error,
        "PORTAPY_NOT_FOUND": not_found,
        "PORTAPY_INVALID_HANDLE": invalid_handle,
        "PORTAPY_INVALID_ARGUMENT": 1,
        "_skip_space": skip_space,
        "_parse_identifier_bounds": parse_identifier,
        "_trim": trim,
        "_fail": fail,
        "_set_status": set_status,
        "_bind_global": bind_global,
        "_scalar_retain_global": retain_global,
        "_scalar_release": release,
        "_host_resolve_host_path": resolve_path,
        "_host_portapy_host_get_attr_span_impl": host_attr,
        "_source_has_definition_or_compound": lambda source, size: False,
        "_source_has_host_call": lambda source, size: False,
        "_exec_host_call_source": downstream,
        "_host_portapy_exec_span_impl": downstream,
        "globals_by_name": globals_by_name,
        "failures": failures,
        "delegated": delegated,
    }
    exec(_helpers(), namespace)
    return namespace


def test_imports_resolve_only_host_registered_modules() -> None:
    namespace = _namespace()
    execute = namespace["_execute_import_statement"]
    globals_by_name = namespace["globals_by_name"]

    assert execute(1, "import helpers as h", 1) == 0
    assert execute(1, "from helpers import answer as imported", 2) == 0
    assert execute(1, "from helpers import nested", 3) == 0

    assert globals_by_name["h"] == 10
    assert globals_by_name["imported"] == 11
    assert globals_by_name["nested"] == 12


def test_import_missing_module_and_star_import_are_structured_failures() -> None:
    namespace = _namespace()
    execute = namespace["_execute_import_statement"]
    failures = namespace["failures"]

    assert execute(1, "import missing", 4) == 5
    assert failures[-1][1:] == (
        "ModuleNotFoundError",
        "No module named 'missing'",
        4,
        1,
    )

    assert execute(1, "from helpers import *", 5) == 2
    assert failures[-1][1] == "ImportError"
    assert "add_all" in failures[-1][2]


def test_import_lines_are_removed_before_normal_execution() -> None:
    namespace = _namespace()
    execute = namespace["_exec_source_with_imports"]
    delegated = namespace["delegated"]

    source = "import helpers\nfrom helpers import answer\nresult = answer + 1\n"
    assert execute(1, source, len(source)) == 0
    assert delegated == ["\n\nresult = answer + 1\n"]


def test_rewrite_replaces_entry_and_emits_parseable_python(tmp_path: Path) -> None:
    path = tmp_path / "generated.py"
    path.write_text(
        "def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:\n"
        "    return 99\n\n"
        "def after() -> int:\n"
        "    return 1\n",
        encoding="utf-8",
    )

    rewrite_generated_imports(path)
    rewritten = path.read_text(encoding="utf-8")
    ast.parse(rewritten)

    assert "_source_has_import_statement" in rewritten
    assert "ModuleNotFoundError" in rewritten
    assert "return 99" not in rewritten
