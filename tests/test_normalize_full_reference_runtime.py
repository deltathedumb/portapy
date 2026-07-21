from __future__ import annotations

from pathlib import Path

import pytest

from tools import normalize_full_reference_runtime as normalizer


def test_replaces_host_traceback_formatter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference_api.py"
    path.write_text(
        "import traceback\n"
        "def capture(error):\n"
        "    return ErrorInfo(\n"
        '            "".join(traceback.format_exception(error)),\n'
        "    )\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)
    assert normalizer.main() == 0
    result = path.read_text(encoding="utf-8")
    assert "import traceback" not in result
    assert "format_exception" not in result
    assert 'type(error).__name__ + ": " + str(error)' in result


def test_rejects_unexpected_traceback_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference_api.py"
    path.write_text("import traceback\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)
    with pytest.raises(RuntimeError, match="one import and one formatter"):
        normalizer.main()
