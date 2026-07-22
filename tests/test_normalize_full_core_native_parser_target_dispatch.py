from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_native_parser_target_dispatch as normalizer


def test_parser_target_dispatch_keeps_expression_in_runtime_box(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "native_ast.py"
    target.write_text(
        '''
class _npr_parser_Parser:
    def _parse_stmt(self):
        __pyinbin_native_expr_values: list[dict] = [self._parse_expr()]
        if self._check("NEWLINE"):
            return ExprStmt(__pyinbin_native_expr_values[0])
        expr: dict = __pyinbin_native_expr_values[0]
        if isinstance(expr, Name):
            return expr
        if isinstance(expr, Subscript):
            return Assign(expr, expr)
        if isinstance(expr, Attr):
            return AugAssign(expr)
        return ExprStmt(expr)
''',
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", target)

    assert normalizer.main() == 0

    source = target.read_text(encoding="utf-8")
    assert "expr: dict" not in source
    assert "isinstance(expr" not in source
    assert "return expr" not in source
    assert source.count("__pyinbin_native_expr_values[0]") >= 8
