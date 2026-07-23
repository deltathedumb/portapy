from __future__ import annotations

from pathlib import Path

from tools import normalize_full_reference_expression_kinds as expression_kinds
from tools import normalize_full_reference_function_return_kinds as return_kinds
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


def _normalized_namespace(tmp_path: Path, monkeypatch) -> dict[str, object]:
    path = tmp_path / "native_full_reference_entry.py"
    path.write_text(_PRELUDE + value_kinds._KIND_HELPERS, encoding="utf-8")
    monkeypatch.setattr(expression_kinds, "PATH", path)
    monkeypatch.setattr(return_kinds, "PATH", path)

    assert expression_kinds.main() == 0
    assert return_kinds.main() == 0

    namespace: dict[str, object] = {}
    exec(path.read_text(encoding="utf-8"), namespace)
    return namespace


def test_mixed_return_kinds_stay_object(tmp_path: Path, monkeypatch) -> None:
    namespace = _normalized_namespace(tmp_path, monkeypatch)
    record = namespace["_native_record_source_kinds"]
    infer = namespace["_native_expression_kind"]

    record(
        1,
        '''def mixed(flag):
    if flag:
        return 7
    return

def never_unmix(flag):
    if flag == 1:
        return 7
    if flag == 2:
        return "seven"
    return 8
''',
    )

    assert infer(1, "mixed(True)") == 7
    assert infer(1, "never_unmix(1)") == 7


def test_consistent_and_none_returns_remain_precise(
    tmp_path: Path,
    monkeypatch,
) -> None:
    namespace = _normalized_namespace(tmp_path, monkeypatch)
    record = namespace["_native_record_source_kinds"]
    infer = namespace["_native_expression_kind"]

    record(
        2,
        '''def consistent(flag):
    if flag:
        return 7
    return 8

def explicit_none():
    return

def no_return():
    pass
''',
    )

    assert infer(2, "consistent(True)") == 2
    assert infer(2, "explicit_none()") == 0
    assert infer(2, "no_return()") == 7


def test_nested_callable_return_uses_single_ledger(
    tmp_path: Path,
    monkeypatch,
) -> None:
    namespace = _normalized_namespace(tmp_path, monkeypatch)
    record = namespace["_native_record_source_kinds"]
    infer = namespace["_native_expression_kind"]

    record(
        3,
        '''def outer():
    def inner():
        return 42
    return inner
''',
    )

    assert infer(3, "outer()") == 6
    assert "_native_function_return_kinds" not in namespace
    assert "_native_record_function_return_kinds" not in namespace
