from __future__ import annotations

from pathlib import Path

import pytest

from tools import normalize_full_core_tracebacks as normalizer


_SOURCE = '''class VirtualMachine:
    def __init__(self) -> None:
        self._synthetic_tracebacks: dict[int, "_PyTBProxy"] = {}

    def read(self, target):
        value = self._synthetic_tracebacks.get(id(target), target.__traceback__)
        return value

    def write(self, frame, exc):
        try:
            pass
        except BaseException as exc:
            if isinstance(exc, BaseException) and not isinstance(exc, PyException):
                tb_frame = _PyTBFrameProxy(frame.code, frame.globals, None)
                prior = self._synthetic_tracebacks.get(id(exc))
                self._synthetic_tracebacks[id(exc)] = _PyTBProxy(tb_frame, prior)
            return exc
'''


def test_disables_host_style_native_traceback_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "vm.py"
    path.write_text(_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    result = path.read_text(encoding="utf-8")
    assert "_synthetic_tracebacks" not in result
    assert "value = None" in result
    assert "_PyTBProxy(tb_frame, prior)" not in result
    assert "return exc" in result


def test_rejects_missing_traceback_storage_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "vm.py"
    path.write_text("class VirtualMachine: pass\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)
    with pytest.raises(RuntimeError, match="traceback table annotation"):
        normalizer.main()
