from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tools import normalize_full_reference_runtime as runtime_normalizer
from tools import normalize_full_reference_type_errors as type_error_normalizer


REFERENCE_SOURCE = Path("src/portapy/reference_api.py")


def _is_vm_run_try(statement: ast.stmt) -> bool:
    return isinstance(statement, ast.Try) and any(
        isinstance(item, ast.Expr)
        and isinstance(item.value, ast.Call)
        and isinstance(item.value.func, ast.Attribute)
        and item.value.func.attr == "run"
        for item in statement.body
    )


def test_type_error_handler_precedes_base_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference_api.py"
    path.write_text(REFERENCE_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(runtime_normalizer, "PATH", path)
    monkeypatch.setattr(type_error_normalizer, "PATH", path)

    assert runtime_normalizer.main() == 0
    assert type_error_normalizer.main() == 0

    module = ast.parse(path.read_text(encoding="utf-8"))
    runtime = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "Runtime"
    )
    method = next(
        node
        for node in runtime.body
        if isinstance(node, ast.FunctionDef) and node.name == "exec_utf8"
    )
    run_try = next(statement for statement in method.body if _is_vm_run_try(statement))
    handler_names = [
        handler.type.id if isinstance(handler.type, ast.Name) else ""
        for handler in run_try.handlers
    ]

    assert handler_names.index("TypeError") < handler_names.index("BaseException")
    type_handler = run_try.handlers[handler_names.index("TypeError")]
    handler_source = ast.unparse(type_handler)
    assert "Status.TYPE_ERROR" in handler_source
    assert "self._capture_native(" in handler_source
