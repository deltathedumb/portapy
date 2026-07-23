from __future__ import annotations

import ast
from pathlib import Path

from tools import materialize_full_reference_entry as materializer
from tools import normalize_full_reference_abi_helpers as abi_normalizer
from tools import normalize_full_reference_errors as error_normalizer
from tools import normalize_full_reference_float_bits as float_normalizer
from tools import normalize_full_reference_nested_kinds as nested_normalizer
from tools import normalize_full_reference_value_kinds as kind_normalizer


def test_removes_top_level_only_kind_guard(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "native_full_reference_entry.py"
    monkeypatch.setattr(materializer, "OUTPUT", output)
    monkeypatch.setattr(abi_normalizer, "PATH", output)
    monkeypatch.setattr(float_normalizer, "PATH", output)
    monkeypatch.setattr(error_normalizer, "PATH", output)
    monkeypatch.setattr(kind_normalizer, "PATH", output)
    monkeypatch.setattr(nested_normalizer, "PATH", output)

    assert materializer.main() == 0
    assert abi_normalizer.main() == 0
    assert float_normalizer.main() == 0
    assert error_normalizer.main() == 0
    assert kind_normalizer.main() == 0
    assert nested_normalizer.main() == 0

    module = ast.parse(output.read_text(encoding="utf-8"))
    scanner = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_native_record_source_kinds"
    )
    text = ast.unparse(scanner)
    assert "if indentation == 0" not in text
    assert text.count("_native_record_statement_kind(runtime, statement)") == 1
