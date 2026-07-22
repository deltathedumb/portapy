from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_expr_stmt_initializer as normalizer


SOURCE = '''@dataclass
class _npr_ast_nodes_ExprStmt:
    expr: dict
    pos: object

class pattern:
    pass

class MatchAs:
    def __init__(self, pattern, name):
        self.pattern = pattern
        self.name = name

class match_case:
    def __init__(self, pattern, guard, body):
        self.pattern = pattern
        self.guard = guard
        self.body = body

class Other:
    pass

def build(value, pos):
    first = _npr_ast_nodes_ExprStmt(expr=value, pos=pos)
    second = MatchAs(pattern=value, name='captured')
    third = match_case(pattern=value, guard=None, body=[])
    return first, second, third
'''


def test_repairs_collision_prone_initializers_and_calls(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "def __init__(self, expr_value: dict, pos: dict) -> None:" in source
    assert "self.expr = expr_value" in source
    assert "def __init__(self, pattern_value, name):" in source
    assert "def __init__(self, pattern_value, guard, body):" in source
    assert source.count("self.pattern = pattern_value") == 2
    assert "_npr_ast_nodes_ExprStmt(expr_value=value, pos=pos)" in source
    assert "MatchAs(pattern_value=value, name='captured')" in source
    assert "match_case(pattern_value=value, guard=None, body=[])" in source
    assert "values: list[dict]" not in source
    ast.parse(source)


def test_positional_constructor_calls_remain_valid(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "native_ast.py"
    source = SOURCE.replace(
        "_npr_ast_nodes_ExprStmt(expr=value, pos=pos)",
        "_npr_ast_nodes_ExprStmt(value, pos)",
    ).replace(
        "MatchAs(pattern=value, name='captured')",
        "MatchAs(value, 'captured')",
    ).replace(
        "match_case(pattern=value, guard=None, body=[])",
        "match_case(value, None, [])",
    )
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0
    rewritten = path.read_text(encoding="utf-8")
    assert "_npr_ast_nodes_ExprStmt(value, pos)" in rewritten
    assert "MatchAs(value, 'captured')" in rewritten
    assert "match_case(value, None, [])" in rewritten
    ast.parse(rewritten)


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


def test_fails_closed_with_existing_initializer(
    tmp_path: Path,
    monkeypatch,
) -> None:
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
