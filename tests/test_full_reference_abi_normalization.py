from __future__ import annotations

import ast
from pathlib import Path

from tools import materialize_full_reference_entry as materializer
from tools import normalize_full_reference_abi_helpers as normalizer


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

    runtime_create = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_portapy_runtime_create_impl"
    )
    runtime_source = ast.unparse(runtime_create)
    assert "instance._vm._seed_builtins(instance._globals)" in runtime_source
    assert "_PortaPyImportLoader(instance)" in runtime_source
    assert "__pyinbin_import__" in runtime_source

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
