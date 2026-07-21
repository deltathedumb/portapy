from __future__ import annotations

from pathlib import Path

import pytest

from tools import normalize_full_reference_runtime as normalizer


def _reference_source() -> str:
    return (
        "import traceback\n"
        "class Runtime:\n"
        "    def __init__(self):\n"
        "        self._values: dict[int, _Slot] = {}\n"
        "    def capture(self, error):\n"
        "        return ErrorInfo(\n"
        '            "".join(traceback.format_exception(error)),\n'
        "        )\n"
        "    def store(self, handle, value):\n"
        "        self._values[handle] = value\n"
        "    def remove(self, handle):\n"
        "        del self._values[handle]\n"
        "    def lookup1(self, handle): return self._values.get(handle)\n"
        "    def lookup2(self, handle): return self._values.get(handle)\n"
        "    def lookup3(self, handle): return self._values.get(handle)\n"
        "    def lookup4(self, handle): return self._values.get(handle)\n"
        "    def lookup5(self, handle): return self._values.get(handle)\n"
        "    def lookup6(self, handle): return self._values.get(handle)\n"
        "    def lookup7(self, handle): return self._values.get(handle)\n"
        "    def lookup8(self, handle): return self._values.get(handle)\n"
        "    def callable(self, callable_handle):\n"
        "        return self._values.get(callable_handle)\n"
    )


def test_replaces_host_tracebacks_and_integer_handle_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference_api.py"
    path.write_text(_reference_source(), encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    result = path.read_text(encoding="utf-8")
    assert "import traceback" not in result
    assert "format_exception" not in result
    assert 'type(error).__name__ + ": " + str(error)' in result
    assert "dict[str, _Slot]" in result
    assert result.count("self._values[str(handle)]") == 2
    assert result.count("self._values.get(str(handle))") == 8
    assert result.count("self._values.get(str(callable_handle))") == 1


def test_rejects_unexpected_reference_runtime_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference_api.py"
    path.write_text("import traceback\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)
    with pytest.raises(RuntimeError, match="traceback formatter normalization"):
        normalizer.main()
