from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tools import materialize_full_reference_entry as materializer
from tools import normalize_full_reference_abi_helpers as abi_normalizer
from tools import normalize_full_reference_container_access as container_normalizer


def _function_source(module: ast.Module, name: str) -> str:
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    return ast.unparse(function)


def test_container_lengths_cross_typed_native_boundaries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "native_full_reference_entry.py"
    monkeypatch.setattr(materializer, "OUTPUT", output)
    monkeypatch.setattr(abi_normalizer, "PATH", output)
    monkeypatch.setattr(container_normalizer, "PATH", output)

    assert materializer.main() == 0
    assert abi_normalizer.main() == 0
    assert container_normalizer.main() == 0

    module = ast.parse(output.read_text(encoding="utf-8"))
    sequence_functions = (
        "_portapy_tuple_set_item_impl",
        "_portapy_tuple_get_size_impl",
        "_portapy_tuple_get_item_impl",
        "_portapy_list_get_size_impl",
        "_portapy_list_get_item_impl",
        "_portapy_list_set_item_impl",
    )
    for name in sequence_functions:
        source = _function_source(module, name)
        assert "_native_sequence_size(" in source
        assert "len(" not in source

    dict_source = _function_source(module, "_portapy_dict_get_size_impl")
    assert "_native_dict_size(target)" in dict_source
    assert "len(" not in dict_source

    sequence_helper = _function_source(module, "_native_sequence_size")
    assert "values: list[object]" in sequence_helper
    assert "return len(values)" in sequence_helper

    dict_helper = _function_source(module, "_native_dict_size")
    assert "values: dict[str, object]" in dict_helper
    assert "return len(values)" in dict_helper

    with pytest.raises(RuntimeError, match="already installed"):
        container_normalizer.main()
