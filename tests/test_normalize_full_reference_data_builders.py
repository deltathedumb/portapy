from __future__ import annotations

import ast
from pathlib import Path

from tools import materialize_full_reference_entry as materializer
from tools import normalize_full_reference_abi_helpers as abi_normalizer
from tools import normalize_full_reference_data_builders as builder_normalizer
from tools import normalize_full_reference_errors as error_normalizer
from tools import normalize_full_reference_float_bits as float_normalizer


def _function(module: ast.Module, name: str) -> str:
    node = next(
        item
        for item in module.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return ast.unparse(node)


def test_installs_sequential_native_data_builders(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "native_full_reference_entry.py"
    monkeypatch.setattr(materializer, "OUTPUT", output)
    monkeypatch.setattr(abi_normalizer, "PATH", output)
    monkeypatch.setattr(float_normalizer, "PATH", output)
    monkeypatch.setattr(error_normalizer, "PATH", output)
    monkeypatch.setattr(builder_normalizer, "PATH", output)

    assert materializer.main() == 0
    assert abi_normalizer.main() == 0
    assert float_normalizer.main() == 0
    assert error_normalizer.main() == 0
    assert builder_normalizer.main() == 0

    module = ast.parse(output.read_text(encoding="utf-8"))
    text = ast.unparse(module)
    assert "_native_byte_data: list[int] = [0]" in text

    builder = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "_DataBuilder"
    )
    builder_text = ast.unparse(builder)
    assert "self.size = size" in builder_text
    assert "self.start = len(_native_byte_data)" in builder_text
    assert "self.written = 0" in builder_text
    assert "self.data" not in builder_text

    materialize = _function(module, "_data_bytes")
    assert "value.written != value.size" in materialize
    assert "data: list[int] = [_native_byte_data[value.start]]" in materialize
    assert "data.append(_native_byte_data[value.start + index])" in materialize

    begin = _function(module, "_portapy_value_from_data_begin_impl")
    assert "instance._store(_DataBuilder(kind, size), _native_kind_member(kind))" in begin

    setter = _function(module, "_portapy_value_set_data_byte_impl")
    assert "index != target.written" in setter
    assert "_native_byte_data.append(byte)" in setter
    assert "target.written += 1" in setter
    assert "target.data" not in setter

    validator = _function(module, "_portapy_value_validate_utf8_impl")
    assert "while index < raw.size" in validator
    assert "invalid UTF-8 leading byte" in validator
    assert "invalid UTF-8 continuation byte" in validator
    assert "codepoint > 1114111" in validator
    assert ".decode(" not in validator
