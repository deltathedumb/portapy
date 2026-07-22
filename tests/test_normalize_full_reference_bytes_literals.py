from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_reference_bytes_literals as normalizer


def _helpers() -> dict[str, object]:
    namespace: dict[str, object] = {
        "_native_byte_data": [0],
        "_native_kind_key": lambda runtime, name: f"g:{runtime}:{name}",
        "_native_builder_key": lambda runtime, handle: f"h:{runtime}:{handle}",
    }
    exec(normalizer._HELPERS, namespace)
    return namespace


def _payload(namespace: dict[str, object], key: str) -> list[int]:
    arena = namespace["_native_byte_data"]
    starts = namespace["_native_literal_start"]
    sizes = namespace["_native_literal_size"]
    start = starts[key]
    size = sizes[key]
    return arena[start : start + size]


def test_parses_bytes_literal_escapes_exactly() -> None:
    namespace = _helpers()
    store = namespace["_native_store_bytes_literal"]

    assert store("hex", 'b"\\x00\\xffA"') is True
    assert _payload(namespace, "hex") == [0, 255, 65]

    assert store("mixed", "b'\\101\\n\\t\\\\\\\''") is True
    assert _payload(namespace, "mixed") == [65, 10, 9, 92, 39]

    assert store("raw", 'rb"\\x41"') is True
    assert _payload(namespace, "raw") == [92, 120, 52, 49]


def test_rejects_non_bytes_and_invalid_hex_literals() -> None:
    namespace = _helpers()
    store = namespace["_native_store_bytes_literal"]

    assert store("text", '"abc"') is False
    assert store("bad", 'b"\\xz0"') is False
    assert "text" not in namespace["_native_literal_start"]
    assert "bad" not in namespace["_native_literal_start"]


def test_attaches_global_and_expression_payloads_to_handles() -> None:
    namespace = _helpers()
    record = namespace["_native_record_global_bytes"]
    attach_global = namespace["_native_attach_global_bytes"]
    attach_expression = namespace["_native_attach_expression_bytes"]

    record(4, "payload", 'b"\\x00\\xffA"')
    attach_global(4, "payload", 9)
    assert _payload(namespace, "h:4:9") == [0, 255, 65]

    attach_expression(4, 'b"eval"', 10)
    assert _payload(namespace, "h:4:10") == [101, 118, 97, 108]


def test_installs_bytes_literal_ledger_into_native_abi(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "native_full_reference_entry.py"
    output.write_text(
        '''def _native_record_statement_kind(runtime, name, text, equals, kind):
    _native_set_global_kind(runtime, name, kind)


def _portapy_get_global_span_impl(runtime, name_text, value, kind):
    if value:
        _native_set_handle_kind(runtime, value, kind)


def _portapy_eval_span_impl(runtime, source_text, value, kind):
    if value:
        _native_set_handle_kind(runtime, value, kind)


def _native_data_size(runtime, handle, kind, value):
    return 0


def _native_data_byte(runtime, handle, kind, value, index):
    return 0
''',
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", output)

    assert normalizer.main() == 0

    module = ast.parse(output.read_text(encoding="utf-8"))
    text = ast.unparse(module)
    assert "_native_record_global_bytes(runtime, name, text[equals + 1:])" in text
    assert "_native_attach_global_bytes(runtime, name_text, value)" in text
    assert "_native_attach_expression_bytes(runtime, source_text, value)" in text
    assert "literal_start = _native_literal_start.get(literal_key, -1)" in text
    assert "_native_byte_data[literal_start + index]" in text
