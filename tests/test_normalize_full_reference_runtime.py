from __future__ import annotations

from pathlib import Path

import pytest

from tools import normalize_full_reference_runtime as normalizer


REFERENCE_SOURCE = Path("src/portapy/reference_api.py")


def test_normalizes_real_reference_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference_api.py"
    path.write_text(REFERENCE_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    result = path.read_text(encoding="utf-8")
    assert "import traceback" not in result
    assert "format_exception" not in result
    assert "type(error).__name__" not in result
    assert "str(error)" not in result
    assert '"PortaPyError"' in result
    assert result.count('"PortaPy operation failed"') == 2

    assert "def _capture_native(" in result
    assert "ErrorInfo(status, type_name, message, message)" in result
    assert "self._error_line = line" in result
    assert "self._error_column = column" in result
    assert result.count("self._error_line = 0") >= 4
    assert result.count("self._error_column = 0") >= 4

    assert "self._values: list[_Slot | None] = [None]" in result
    assert "kind: ValueKind = ValueKind.INT" in result
    assert "self._values.append(_Slot(value, kind))" in result
    assert "def _value_slot(self, handle: int) -> _Slot | None:" in result
    assert "if handle <= 0 or handle >= len(self._values):" in result
    assert result.count("self._value_slot(handle)") == 8
    assert result.count("self._value_slot(callable_handle)") == 1
    assert "self._values[handle] = None" in result
    assert "str(handle)" not in result
    assert "dict[str, _Slot]" not in result

    assert "self._store(None, ValueKind.NONE)" in result
    assert "self._store(value, ValueKind.BOOL)" in result
    assert "self._store(value, ValueKind.INT)" in result
    assert "self._store(value, ValueKind.FLOAT)" in result
    assert "self._store(value, ValueKind.STRING)" in result
    assert "self._store(value, ValueKind.BYTES)" in result

    assert "return Status.OK, slot.kind" in result
    assert "slot.kind is not ValueKind.INT" in result
    assert "slot.kind is not ValueKind.FLOAT" in result
    assert "slot.kind is not ValueKind.STRING" in result
    assert "type(slot.value)" not in result


def test_native_value_slots_use_stable_integer_indices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference_api.py"
    path.write_text(REFERENCE_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0
    namespace: dict[str, object] = {}
    # The complete module has package-relative imports, so execute only the
    # normalized Runtime storage methods in a tiny compatible shell.
    source = path.read_text(encoding="utf-8")
    runtime_start = source.index("class Runtime:")
    runtime_source = source[runtime_start:]
    prefix = '''
from dataclasses import dataclass
from enum import IntEnum
class Status(IntEnum):
    OK = 0
    INVALID_HANDLE = 7
class ValueKind(IntEnum):
    INT = 2
@dataclass
class _Slot:
    value: object
    kind: ValueKind = ValueKind.INT
    refs: int = 1
'''
    # Keep just the methods needed for storage semantics.
    store_start = runtime_source.index("    def _store(")
    close_start = runtime_source.index("    def close(")
    methods = runtime_source[store_start:close_start]
    exec(prefix + "\nclass Probe:\n" + methods, namespace)
    probe = namespace["Probe"]()
    probe._values = [None]
    probe._next = 1
    first = probe._store("first")
    second = probe._store("second")
    assert (first, second) == (1, 2)
    assert probe._value_slot(first).value == "first"
    assert probe._value_slot(second).value == "second"
    assert probe._value_slot(0) is None
    assert probe._value_slot(99) is None


def test_rejects_unexpected_reference_runtime_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference_api.py"
    path.write_text("import traceback\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)
    with pytest.raises(RuntimeError, match="error capture normalization"):
        normalizer.main()
