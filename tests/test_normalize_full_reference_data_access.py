from __future__ import annotations

import ast
from pathlib import Path

from tools import materialize_full_reference_entry as materializer
from tools import normalize_full_reference_abi_helpers as abi_normalizer
from tools import normalize_full_reference_data_access as access_normalizer
from tools import normalize_full_reference_data_builders as builder_normalizer
from tools import normalize_full_reference_errors as error_normalizer
from tools import normalize_full_reference_float_bits as float_normalizer


class _DataBuilder:
    pass


def _helpers() -> dict[str, object]:
    namespace: dict[str, object] = {
        "_DataBuilder": _DataBuilder,
        "_native_byte_data": [0],
    }
    exec(access_normalizer._HELPERS, namespace)
    return namespace


def test_calculates_utf8_size_and_bytes_without_encoding() -> None:
    namespace = _helpers()
    size = namespace["_native_data_size"]
    byte = namespace["_native_data_byte"]
    value = "Aπ😀"
    expected = value.encode("utf-8")
    assert size(value) == len(expected)
    assert bytes(byte(value, index) for index in range(len(expected))) == expected
    raw = b"\x00\xffA"
    assert size(raw) == 3
    assert [byte(raw, index) for index in range(3)] == [0, 255, 65]


def test_installs_direct_data_access_into_native_abi(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "native_full_reference_entry.py"
    monkeypatch.setattr(materializer, "OUTPUT", output)
    monkeypatch.setattr(abi_normalizer, "PATH", output)
    monkeypatch.setattr(float_normalizer, "PATH", output)
    monkeypatch.setattr(error_normalizer, "PATH", output)
    monkeypatch.setattr(builder_normalizer, "PATH", output)
    monkeypatch.setattr(access_normalizer, "PATH", output)

    assert materializer.main() == 0
    assert abi_normalizer.main() == 0
    assert float_normalizer.main() == 0
    assert error_normalizer.main() == 0
    assert builder_normalizer.main() == 0
    assert access_normalizer.main() == 0

    module = ast.parse(output.read_text(encoding="utf-8"))
    text = ast.unparse(module)
    assert "_native_string_byte(value, index)" in text
    assert "size = _native_data_size(raw)" in text
    assert "result = _native_data_byte(raw, index)" in text
    functions = "\n".join(
        ast.unparse(node)
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {
            "_portapy_value_get_size_impl",
            "_portapy_value_get_byte_impl",
        }
    )
    assert ".encode(" not in functions
    assert "_data_bytes(" not in functions
