from __future__ import annotations

import ast
from pathlib import Path

from tools import materialize_full_reference_entry as materializer
from tools import normalize_full_reference_abi_helpers as abi_normalizer
from tools import normalize_full_reference_float_bits as float_normalizer


def _function(module: ast.Module, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_rewrites_native_float_functions_to_integer_bits(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "native_full_reference_entry.py"
    monkeypatch.setattr(materializer, "OUTPUT", output)
    monkeypatch.setattr(abi_normalizer, "PATH", output)
    monkeypatch.setattr(float_normalizer, "PATH", output)

    assert materializer.main() == 0
    assert abi_normalizer.main() == 0
    assert float_normalizer.main() == 0

    module = ast.parse(output.read_text(encoding="utf-8"))
    names = {
        node.name
        for node in module.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "_portapy_value_from_f64_impl" not in names
    assert "_portapy_value_as_f64_impl" not in names

    constructor = _function(module, "_portapy_value_from_f64_bits_impl")
    conversion = _function(module, "_portapy_value_as_f64_bits_impl")
    assert constructor.args.args[1].arg == "bits"
    assert ast.unparse(constructor.args.args[1].annotation) == "int"
    assert "instance._store(bits, ValueKind.FLOAT)" in ast.unparse(constructor)
    assert "kind is not ValueKind.FLOAT" in ast.unparse(conversion)
    assert "instance.unbox(value)" in ast.unparse(conversion)
