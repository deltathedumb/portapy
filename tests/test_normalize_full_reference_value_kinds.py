from __future__ import annotations

import ast
from pathlib import Path

from tools import materialize_full_reference_entry as materializer
from tools import normalize_full_reference_abi_helpers as abi_normalizer
from tools import normalize_full_reference_errors as error_normalizer
from tools import normalize_full_reference_float_bits as float_normalizer
from tools import normalize_full_reference_value_kinds as kind_normalizer


_CONSTANTS = {
    "PORTAPY_VALUE_NONE": 0,
    "PORTAPY_VALUE_BOOL": 1,
    "PORTAPY_VALUE_INT": 2,
    "PORTAPY_VALUE_FLOAT": 3,
    "PORTAPY_VALUE_STRING": 4,
    "PORTAPY_VALUE_BYTES": 5,
    "PORTAPY_VALUE_CALLABLE": 6,
    "PORTAPY_VALUE_OBJECT": 7,
    "PORTAPY_VALUE_TUPLE": 8,
    "PORTAPY_VALUE_DICT": 9,
    "PORTAPY_VALUE_LIST": 10,
}


class _Kinds:
    NONE = object()
    BOOL = object()
    INT = object()
    FLOAT = object()
    STRING = object()
    BYTES = object()
    CALLABLE = object()
    OBJECT = object()
    TUPLE = object()
    DICT = object()
    LIST = object()


def _helpers() -> dict[str, object]:
    namespace: dict[str, object] = dict(_CONSTANTS)
    namespace["Runtime"] = object
    namespace["ValueKind"] = _Kinds
    exec(kind_normalizer._KIND_HELPERS, namespace)
    return namespace


def test_records_top_level_literal_alias_and_callable_kinds() -> None:
    namespace = _helpers()
    record = namespace["_native_record_source_kinds"]
    get_kind = namespace["_native_global_kind"]
    record(
        3,
        "nothing = None\n"
        "flag = True\n"
        "name = 'Somnia'\n"
        "payload = b'\\x00A'\n"
        "alias = name\n"
        "punctuation = 'a;b#c'; answer = 40 + 2\n"
        "items = [1, 2]\n"
        "pair = (1, 2)\n"
        "mapping = {'x': 1}\n"
        "def work(value):\n    local = value\n    return local\n"
        "class Widget:\n    pass\n",
    )
    assert get_kind(3, "nothing") == 0
    assert get_kind(3, "flag") == 1
    assert get_kind(3, "name") == 4
    assert get_kind(3, "payload") == 5
    assert get_kind(3, "alias") == 4
    assert get_kind(3, "punctuation") == 4
    assert get_kind(3, "answer") == 2
    assert get_kind(3, "items") == 10
    assert get_kind(3, "pair") == 8
    assert get_kind(3, "mapping") == 9
    assert get_kind(3, "work") == 6
    assert get_kind(3, "Widget") == 6
    assert get_kind(3, "local") == 2


def test_infers_eval_result_kinds() -> None:
    namespace = _helpers()
    infer = namespace["_native_expression_kind"]
    set_kind = namespace["_native_set_global_kind"]
    set_kind(1, "text", 4)
    set_kind(1, "number", 2)
    assert infer(1, "None") == 0
    assert infer(1, "False") == 1
    assert infer(1, "3.5") == 3
    assert infer(1, "text") == 4
    assert infer(1, "text + '!' ") == 4
    assert infer(1, "number + 8") == 2
    assert infer(1, "number > 1") == 1


def test_installs_kind_ledger_into_native_abi(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "native_full_reference_entry.py"
    monkeypatch.setattr(materializer, "OUTPUT", output)
    monkeypatch.setattr(abi_normalizer, "PATH", output)
    monkeypatch.setattr(float_normalizer, "PATH", output)
    monkeypatch.setattr(error_normalizer, "PATH", output)
    monkeypatch.setattr(kind_normalizer, "PATH", output)

    assert materializer.main() == 0
    assert abi_normalizer.main() == 0
    assert float_normalizer.main() == 0
    assert error_normalizer.main() == 0
    assert kind_normalizer.main() == 0

    module = ast.parse(output.read_text(encoding="utf-8"))
    text = ast.unparse(module)
    assert "_native_record_source_kinds(runtime, source_text)" in text
    assert "_native_expression_kind(runtime, source_text)" in text
    assert "_native_global_kind(runtime, name_text)" in text
    assert "slot.kind = _native_kind_member(kind)" in text
