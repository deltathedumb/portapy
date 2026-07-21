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

    assert "dict[str, _Slot]" in result
    assert "kind: ValueKind = ValueKind.INT" in result
    assert "self._values[str(handle)] = _Slot(value, kind)" in result
    assert result.count("self._values.get(str(handle))") == 8
    assert result.count("self._values.get(str(callable_handle))") == 1
    assert "del self._values[str(handle)]" in result

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


def test_rejects_unexpected_reference_runtime_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference_api.py"
    path.write_text("import traceback\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)
    with pytest.raises(RuntimeError, match="error capture normalization"):
        normalizer.main()
