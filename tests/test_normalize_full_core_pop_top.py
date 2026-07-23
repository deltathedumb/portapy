from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_pop_top as normalizer


FRONTEND_SOURCE = '''class _Lowerer:
    def first(self):
        self.emit(Op.POP_TOP)

    def second(self, condition):
        if condition:
            self.emit(Op.POP_TOP)

    def third(self, condition):
        if condition:
            if condition:
                self.emit(Op.POP_TOP)

    def fourth(self):
        self.emit(Op.POP_TOP)

    def fifth(self):
        self.emit(Op.POP_TOP)
'''


def test_inlines_all_discard_emissions_with_original_indentation(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "frontend.py"
    path.write_text(FRONTEND_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "self.emit(Op.POP_TOP)" not in source
    assert "def discard_top" not in source
    assert source.count('self.name_index("__pyinbin_internal_discard")') == 10
    assert source.count("Op.STORE_NAME,") == 5
    assert source.count("Op.DELETE_NAME,") == 5
    ast.parse(source)


def test_fails_closed_when_emission_count_changes(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "frontend.py"
    path.write_text(
        FRONTEND_SOURCE.replace("        self.emit(Op.POP_TOP)\n", "", 1),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "expected 5 emissions" in str(error)
    else:
        raise AssertionError("normalizer accepted an unexpected POP_TOP count")
