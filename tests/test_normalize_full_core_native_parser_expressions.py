from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_native_parser_expressions as normalizer


SOURCE = '''class _npr_ast_nodes_ExprStmt:
    expr: "Expr"
    pos: object

class _npr_parser_Parser:
    def _parse_stmt(self):
        pos = self._peek().pos
        expr = self._parse_expr()
        if isinstance(expr, Name):
            return expr
        if condition:
            value = self._parse_expr()
        other = self._peek()
        return expr

    def another_method(self):
        untouched = self._parse_expr()
        return untouched
'''


def test_types_results_field_and_fast_paths_expression_statements(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "class _npr_ast_nodes_ExprStmt:" in source
    assert "expr: dict" in source
    assert "expr: dict = self._parse_expr()" in source
    assert "value: dict = self._parse_expr()" in source
    assert "untouched = self._parse_expr()" in source
    assert "other = self._peek()" in source
    assert "if self._check('NEWLINE'):" in source
    assert "self._eat()" in source
    assert "return _npr_ast_nodes_ExprStmt(expr=expr, pos=pos)" in source
    assert source.index("if self._check('NEWLINE'):") < source.index(
        "if isinstance(expr, Name):"
    )
    ast.parse(source)


def test_fails_closed_without_parser_method(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(
        'class _npr_ast_nodes_ExprStmt:\n    expr: "Expr"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "Parser class is missing" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing embedded parser")


def test_fails_closed_without_expr_stmt_field(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(
        SOURCE.replace('    expr: "Expr"\n', "    value: object\n"),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "ExprStmt.expr expected one field" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing ExprStmt.expr field")


def test_fails_closed_without_main_expr_assignment(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(
        SOURCE.replace("        expr = self._parse_expr()\n", "        expr = 1\n"),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "fast path expected one insertion" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing expression fast path")
