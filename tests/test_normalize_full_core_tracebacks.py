from __future__ import annotations

from pathlib import Path

import pytest

from tools import normalize_full_core_tracebacks as normalizer


_SOURCE = '''class VirtualMachine:
    def __init__(self) -> None:
        self._synthetic_tracebacks: dict[int, "_PyTBProxy"] = {}

    def read(self, target):
        return self._synthetic_tracebacks.get(id(target), target.__traceback__)

    def write(self, exc, tb_frame):
        prior = self._synthetic_tracebacks.get(id(exc))
        self._synthetic_tracebacks[id(exc)] = _PyTBProxy(tb_frame, prior)
'''


def test_uses_string_keys_for_native_tracebacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "vm.py"
    path.write_text(_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    result = path.read_text(encoding="utf-8")
    assert 'dict[str, "_PyTBProxy"]' in result
    assert "get(str(id(target))" in result
    assert "get(str(id(exc)))" in result
    assert "[str(id(exc))]" in result
    assert "[id(exc)]" not in result


def test_rejects_missing_traceback_storage_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "vm.py"
    path.write_text("class VirtualMachine: pass\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)
    with pytest.raises(RuntimeError, match="traceback table annotation"):
        normalizer.main()
