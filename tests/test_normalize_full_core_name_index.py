from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_name_index as normalizer


SOURCE = '''class _Lowerer:
    def name_index(self, value: str) -> int:
        try:
            return self.names.index(value)
        except ValueError:
            self.names.append(value)
            return len(self.names) - 1
'''


def test_replaces_exception_lookup_with_direct_loop(
    tmp_path: Path, monkeypatch,
) -> None:
    path = tmp_path / "frontend.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "while index < len(self.names):" in source
    assert "if self.names[index] == value:" in source
    assert "self.names.append(value)" in source
    assert ".names.index(" not in source
    namespace: dict[str, object] = {}
    exec(source, namespace)
    lowerer = namespace["_Lowerer"]()
    lowerer.names = ["alpha"]
    assert lowerer.name_index("alpha") == 0
    assert lowerer.name_index("beta") == 1
    assert lowerer.names == ["alpha", "beta"]


def test_fails_closed_when_shape_changes(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "frontend.py"
    path.write_text("class _Lowerer:\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "expected one exception lookup" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing name_index implementation")
