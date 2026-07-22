from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_pop_top as normalizer


FRONTEND_SOURCE = '''class _Lowerer:
    def emit(self, op, arg=0):
        self.instructions.append(Instruction(op, arg))
        return len(self.instructions) - 1

    def patch(self, offset: int, target: int) -> None:
        return

    def first(self):
        self.emit(Op.POP_TOP)

    def second(self):
        self.emit(Op.POP_TOP)

    def third(self):
        self.emit(Op.POP_TOP)

    def fourth(self):
        self.emit(Op.POP_TOP)

    def fifth(self):
        self.emit(Op.POP_TOP)
'''


def test_lowers_all_pop_top_emissions_to_internal_bindings(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "frontend.py"
    path.write_text(FRONTEND_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "self.emit(Op.POP_TOP)" not in source
    assert source.count("self.discard_top()") == 5
    assert "def discard_top(self) -> None:" in source
    assert 'discard_name = f"<discard:{len(self.instructions)}>"' in source
    assert "self.emit(Op.STORE_NAME, discard_index)" in source
    assert "self.emit(Op.DELETE_NAME, discard_index)" in source


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
