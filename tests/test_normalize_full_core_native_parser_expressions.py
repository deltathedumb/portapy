from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_native_parser_expressions as normalizer


SOURCE = '''class _npr_parser_Parser:
    def _parse_stmt(self):
        expr = self._parse_expr()
        if condition:
            value = self._parse_expr()
        other = self._peek()
        return expr

    def another_method(self):
        untouched = self._parse_expr()
        return untouched
'''


def test_types_parse_stmt_expression_results_only(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "expr: object = self._parse_expr()" in source
    assert "value: object = self._parse_expr()" in source
    assert "untouched = self._parse_expr()" in source
    assert "other = self._peek()" in source
    ast.parse(source)


def test_fails_closed_without_parser_method(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text("class Other:\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "Parser class is missing" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing embedded parser")
