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


class _Kinds:
    STRING = object()
    BYTES = object()


def _helpers() -> dict[str, object]:
    namespace: dict[str, object] = {
        "_DataBuilder": _DataBuilder,
        "ValueKind": _Kinds,
        "_native_byte_data": [0],
    }
    exec(access_normalizer._HELPERS, namespace)
    return namespace


def test_calculates_utf8_size_and_bytes_without_introspection() -> None:
    namespace = _helpers()
    size = namespace["_native_data_size"]
    byte = namespace["_native_data_byte"]
    value = "Aπ😀"
    expected = value.encode("utf-8")
    assert size(1, 2, _Kinds.STRING, value) == len(expected)
    assert bytes(
        byte(1, 2, _Kinds.STRING, value, index)
        for index in range(len(expected))
    ) == expected
    raw = b"\x00\xffA"
    assert size(1, 3, _Kinds.BYTES, raw) == 3
    assert [
        byte(1, 3, _Kinds.BYTES, raw, index)
        for index in range(3)
    ] == [0, 255, 65]


def test_builder_handle_uses_arena_without_payload_type_checks() -> None:
    namespace = _helpers()
    size = namespace["_native_data_size"]
    byte = namespace["_native_data_byte"]
    key = namespace["_native_builder_key"]
    markers = namespace["_native_builder_handles"]
    arena = namespace["_native_byte_data"]
    builder = _DataBuilder()
    builder.start = len(arena)
    builder.size = 2
    builder.written = 2
    arena.extend([10, 255])
    markers[key(4, 7)] = True
    assert size(4, 7, _Kinds.STRING, builder) == 2
    assert byte(4, 7, _Kinds.STRING, builder, 0) == 10
    assert byte(4, 7, _Kinds.STRING, builder, 1) == 255


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
    assert "_native_builder_handles[_native_builder_key(runtime, result)] = True" in text
    assert "_native_string_byte(value, index)" in text
    assert "size = _native_data_size(runtime, value, kind, raw)" in text
    assert "result = _native_data_byte(runtime, value, kind, raw, index)" in text
    functions = "\n".join(
        ast.unparse(node)
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {
            "_portapy_value_get_size_impl",
            "_portapy_value_get_byte_impl",
        }
    )
    assert "type(raw)" not in functions
    assert "isinstance(raw" not in functions
