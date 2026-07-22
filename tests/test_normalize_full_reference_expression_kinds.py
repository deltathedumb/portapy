from __future__ import annotations

from pathlib import Path

from tools import normalize_full_reference_expression_kinds as normalizer
from tools import normalize_full_reference_value_kinds as value_kinds


_PRELUDE = '''
PORTAPY_VALUE_NONE = 0
PORTAPY_VALUE_BOOL = 1
PORTAPY_VALUE_INT = 2
PORTAPY_VALUE_FLOAT = 3
PORTAPY_VALUE_STRING = 4
PORTAPY_VALUE_BYTES = 5
PORTAPY_VALUE_CALLABLE = 6
PORTAPY_VALUE_OBJECT = 7
PORTAPY_VALUE_TUPLE = 8
PORTAPY_VALUE_DICT = 9
PORTAPY_VALUE_LIST = 10

class Runtime:
    pass

class ValueKind:
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

'''


def _normalized_helpers(tmp_path: Path, monkeypatch) -> dict[str, object]:
    path = tmp_path / "native_full_reference_entry.py"
    path.write_text(_PRELUDE + value_kinds._KIND_HELPERS, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    namespace: dict[str, object] = {}
    exec(path.read_text(encoding="utf-8"), namespace)
    return namespace


def test_literal_left_comparison_is_boolean(tmp_path: Path, monkeypatch) -> None:
    namespace = _normalized_helpers(tmp_path, monkeypatch)
    infer = namespace["_native_expression_kind"]

    assert infer(1, '"abc" < "abd"') == 1
    assert infer(1, '("abc" < "abd")') == 1
    assert infer(1, "'a < b'") == 4


def test_boolops_keep_operand_kinds(tmp_path: Path, monkeypatch) -> None:
    namespace = _normalized_helpers(tmp_path, monkeypatch)
    infer = namespace["_native_expression_kind"]
    set_kind = namespace["_native_set_global_kind"]

    set_kind(7, "empty", 4)
    set_kind(7, "name", 4)
    set_kind(7, "answer", 2)

    assert infer(7, "empty or name") == 4
    assert infer(7, "name and answer") == 2
    assert infer(7, 'answer > 40 and name == "Somnia"') == 1
    assert infer(7, "not empty") == 1


def test_source_functions_propagate_return_kinds(tmp_path: Path, monkeypatch) -> None:
    namespace = _normalized_helpers(tmp_path, monkeypatch)
    infer = namespace["_native_expression_kind"]
    record = namespace["_native_record_source_kinds"]
    global_kind = namespace["_native_global_kind"]

    source = '''def seven():
    return 7
def label():
    return "ready"
def make_items():
    return [1, 2]
class Box:
    pass
answer = seven()
text = label()
items = make_items()
box = Box()
'''
    record(9, source)

    assert infer(9, "seven()") == 2
    assert infer(9, "label()") == 4
    assert infer(9, "make_items()") == 10
    assert infer(9, "Box()") == 7
    assert global_kind(9, "answer") == 2
    assert global_kind(9, "text") == 4
    assert global_kind(9, "items") == 10
    assert global_kind(9, "box") == 7


def test_nested_function_return_is_callable(tmp_path: Path, monkeypatch) -> None:
    namespace = _normalized_helpers(tmp_path, monkeypatch)
    infer = namespace["_native_expression_kind"]
    record = namespace["_native_record_source_kinds"]

    source = '''def outer(base):
    def inner(value):
        return base + value
    return inner
fn = outer(19)
'''
    record(11, source)

    assert infer(11, "outer(19)") == 6
    assert infer(11, "fn") == 6
