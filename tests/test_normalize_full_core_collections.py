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


def _assert_restored(result: str) -> None:
    assert "frame.stack.append(None)" not in result
    assert "frame.stack.append(tuple(values))" in result
    assert "frame.stack.append(set(values))" in result


def test_restores_canonical_collection_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_restored(
        _run(tmp_path, monkeypatch, collections._CANONICAL_BOOTSTRAP)
    )


def test_restores_compact_collection_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run(tmp_path, monkeypatch, collections._COMPACT_BOOTSTRAP)
    _assert_restored(result)
    assert "if instr.arg: del frame.stack[-instr.arg:]" in result


def test_rejects_ambiguous_collection_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "vm.py"
    path.write_text(
        collections._CANONICAL_BOOTSTRAP + collections._COMPACT_BOOTSTRAP,
        encoding="utf-8",
    )
    monkeypatch.setattr(collections, "PATH", path)
    with pytest.raises(RuntimeError, match="expected one BUILD_TUPLE/BUILD_SET block"):
        collections.main()


def test_rejects_collection_block_without_placeholder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = collections._CANONICAL_BOOTSTRAP.replace(
        "frame.stack.append(None)", "frame.stack.append(values)"
    )
    path = tmp_path / "vm.py"
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(collections, "PATH", path)
    with pytest.raises(RuntimeError, match="placeholder collection result"):
        collections.main()
