from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_expr_stmt_initializer as normalizer


SOURCE = '''@dataclass
class _npr_ast_nodes_ExprStmt:
    expr: dict
    pos: object

class Other:
    pass
'''


def test_installs_direct_explicit_initializer(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "def __init__(self, expr: dict, pos: dict) -> None:" in source
    assert "self.expr = expr" in source
    assert "self.pos = pos" in source
    assert "values: list[dict]" not in source
    ast.parse(source)


def test_fails_closed_without_expr_stmt_class(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text("class Other:\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "expected one class" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing ExprStmt class")


def test_fails_closed_with_existing_initializer(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(
        SOURCE.replace(
            "    pos: object\n",
            "    pos: object\n\n    def __init__(self):\n        pass\n",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "already has an initializer" in str(error)
    else:
        raise AssertionError("normalizer replaced an existing initializer")
