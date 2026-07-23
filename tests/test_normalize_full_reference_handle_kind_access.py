from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_reference_handle_kind_access as normalizer


SOURCE = '''def _native_set_handle_kind(instance: Runtime, handle: int, kind: int) -> bool:
    slot = instance._values.get(str(handle))
    if slot is None:
        return False
    slot.kind = _native_kind_member(kind)
    return True
'''


def test_uses_normalized_value_slot_accessor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "native_full_reference_entry.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "slot = instance._value_slot(handle)" in source
    assert "slot.kind = _native_kind_member(kind)" in source
    assert "instance._values" not in source
    assert ".get(str(handle))" not in source
    ast.parse(source)


def test_fails_closed_when_stale_shape_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "native_full_reference_entry.py"
    path.write_text(
        SOURCE.replace(
            "instance._values.get(str(handle))",
            "instance._value_slot(handle)",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "stale dict lookup" in str(error)
    else:
        raise AssertionError("normalizer accepted an unexpected helper shape")
