from __future__ import annotations

from pathlib import Path

import pytest

from tools import normalize_full_core_collections as collections


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str) -> str:
    path = tmp_path / "vm.py"
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(collections, "PATH", path)
    assert collections.main() == 0
    return path.read_text(encoding="utf-8")


def test_restores_canonical_collection_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run(tmp_path, monkeypatch, collections._CANONICAL_BOOTSTRAP)
    assert result == collections._RESTORED


def test_restores_compact_collection_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run(tmp_path, monkeypatch, collections._COMPACT_BOOTSTRAP)
    assert result == collections._RESTORED


def test_rejects_missing_or_ambiguous_collection_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "vm.py"
    path.write_text(
        collections._CANONICAL_BOOTSTRAP + collections._COMPACT_BOOTSTRAP,
        encoding="utf-8",
    )
    monkeypatch.setattr(collections, "PATH", path)
    with pytest.raises(RuntimeError, match="expected one verified source form"):
        collections.main()
