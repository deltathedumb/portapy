from __future__ import annotations

import ast
from pathlib import Path

from tools import materialize_full_reference_entry as materializer
from tools import normalize_full_reference_abi_helpers as abi_normalizer
from tools import normalize_full_reference_errors as error_normalizer


def _function(module: ast.Module, name: str) -> str:
    node = next(
        item
        for item in module.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return ast.unparse(node)


def test_installs_native_structured_error_paths(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "native_full_reference_entry.py"
    monkeypatch.setattr(materializer, "OUTPUT", output)
    monkeypatch.setattr(abi_normalizer, "PATH", output)
    monkeypatch.setattr(error_normalizer, "PATH", output)

    assert materializer.main() == 0
    assert abi_normalizer.main() == 0
    assert error_normalizer.main() == 0

    module = ast.parse(output.read_text(encoding="utf-8"))
    validate = _function(module, "_portapy_value_validate_utf8_impl")
    assert "UnicodeDecodeError" in validate
    assert "instance._capture_native(" in validate

    execute = _function(module, "_portapy_exec_span_impl")
    evaluate = _function(module, "_portapy_eval_span_impl")
    assert "_native_error_location(source_text)" in execute
    assert "_native_error_location(source_text)" in evaluate
    assert "RuntimeError" in execute
    assert "SyntaxError" in evaluate

    line = _function(module, "_portapy_error_line_impl")
    column = _function(module, "_portapy_error_column_impl")
    assert "return instance._error_line" in line
    assert "return instance._error_column" in column


def test_native_error_location_finds_division_by_zero() -> None:
    namespace: dict[str, object] = {}
    exec(error_normalizer._LOCATION_HELPER, namespace)
    locate = namespace["_native_error_location"]

    assert locate("safe = 1\nbroken = 5 // 0") == (2, 12)
    assert locate("value = 9 % 0") == (1, 11)
    assert locate("value = 4") == (1, 1)
