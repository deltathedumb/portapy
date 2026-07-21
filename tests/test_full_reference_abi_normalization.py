from __future__ import annotations

import ast
from pathlib import Path

from tools import materialize_full_reference_entry as materializer
from tools import normalize_full_reference_abi_helpers as normalizer


def _function(module: ast.Module, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_full_reference_normalization_installs_runtime_support(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "native_full_reference_entry.py"
    monkeypatch.setattr(materializer, "OUTPUT", output)
    monkeypatch.setattr(normalizer, "PATH", output)

    assert materializer.main() == 0
    assert normalizer.main() == 0

    source = output.read_text(encoding="utf-8")
    module = ast.parse(source)
    classes = {
        node.name
        for node in module.body
        if isinstance(node, ast.ClassDef)
    }
    assert "_PortaPyImportLoader" in classes
    assert "source_size > len(source)" not in source

    runtime_source = ast.unparse(_function(module, "_portapy_runtime_create_impl"))
    assert "instance._vm._seed_builtins(instance._globals)" in runtime_source
    assert "_PortaPyImportLoader(instance)" in runtime_source
    assert "__pyinbin_import__" in runtime_source

    kind_source = ast.unparse(_function(module, "_portapy_value_get_kind_impl"))
    assert "instance.value_kind(value)" in kind_source
    assert "return int(kind)" in kind_source
    assert "instance.unbox(value)" not in kind_source
    assert "_value_kind(" not in kind_source

    bool_source = ast.unparse(_function(module, "_portapy_value_as_bool_impl"))
    assert "instance.value_kind(value)" in bool_source
    assert "kind is not ValueKind.BOOL" in bool_source
    assert "instance.unbox(value)" in bool_source
    assert "type(target)" not in bool_source

    loader = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef)
        and node.name == "_PortaPyImportLoader"
    )
    loader_source = ast.unparse(loader)
    assert "self.instance.read_global(parts[0])" in loader_source
    assert "getattr(value, parts[index])" in loader_source
    assert "raise ImportError(name)" in loader_source
    assert "ModuleNotFoundError" not in loader_source
