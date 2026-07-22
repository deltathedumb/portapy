from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_pop_top as normalizer


FRONTEND_SOURCE = '''class Lowerer:
    def stmt(self, node):
        if isinstance(node, ast.Expr):
            self.expr(node.value)
            if not self.interactive and not isinstance(node.value, ast.Yield):
                self.emit(Op.POP_TOP)
        elif isinstance(node, ast.Pass):
            return
'''


def test_preserves_expression_evaluation_without_pop_top(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "frontend.py"
    path.write_text(FRONTEND_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "self.expr(node.value)" in source
    assert "self.emit(Op.POP_TOP)" not in source
    assert "elif isinstance(node, ast.Pass):" in source


def test_fails_closed_without_unique_emission(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "frontend.py"
    path.write_text("def stmt():\n    return\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "expected one emission" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing POP_TOP emission")
