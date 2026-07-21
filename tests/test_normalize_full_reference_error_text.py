from __future__ import annotations

import ast
from pathlib import Path

from tools import materialize_full_reference_entry as materializer
from tools import normalize_full_reference_abi_helpers as abi_normalizer
from tools import normalize_full_reference_error_text as text_normalizer


def _function(module: ast.Module, name: str) -> str:
    return ast.unparse(
        next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
    )


def test_rewrites_error_text_helpers_without_encoding(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "native_full_reference_entry.py"
    monkeypatch.setattr(materializer, "OUTPUT", output)
    monkeypatch.setattr(abi_normalizer, "PATH", output)
    monkeypatch.setattr(text_normalizer, "PATH", output)

    assert materializer.main() == 0
    assert abi_normalizer.main() == 0
    assert text_normalizer.main() == 0

    module = ast.parse(output.read_text(encoding="utf-8"))
    type_size = _function(module, "_portapy_error_type_size_impl")
    message_size = _function(module, "_portapy_error_message_size_impl")
    type_byte = _function(module, "_portapy_error_type_byte_impl")
    message_byte = _function(module, "_portapy_error_message_byte_impl")

    assert "len(error.type_name)" in type_size
    assert "len(error.message)" in message_size
    assert "ord(error.type_name[index])" in type_byte
    assert "ord(error.message[index])" in message_byte
    combined = type_size + message_size + type_byte + message_byte
    assert ".encode(" not in combined
    assert "_error_bytes(" not in combined
