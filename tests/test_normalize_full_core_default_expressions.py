from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_default_expressions as normalizer


SOURCE = '''class Parser:
    def _parse_optional_default(self):
        if not self._check("OP", "="):
            return None
        self._eat()
        return self._parse_default_literal()
'''


def test_uses_full_expression_parser(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "return self._parse_expr()" in source
    assert "return self._parse_default_literal()" not in source
    ast.parse(source)


def test_fails_closed_when_parser_shape_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(
        SOURCE.replace("self._parse_default_literal()", "self._parse_expr()"),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "restricted literal path" in str(error)
    else:
        raise AssertionError("normalizer accepted an unexpected parser shape")
