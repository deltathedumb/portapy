from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_pattern_constructor_collisions as normalizer


SOURCE = '''class pattern:
    pass

class MatchAs:
    def __init__(self, pattern: pattern | None = None, name: str | None = None):
        self.pattern = pattern
        self.name = name

class match_case:
    def __init__(self, pattern: pattern, guard: object, body: list):
        self.pattern = pattern
        self.guard = guard
        self.body = body

def build(value):
    first = MatchAs(pattern=value, name='captured')
    second = match_case(pattern=value, guard=None, body=[])
    return first, second
'''


def test_repairs_pattern_parameters_and_keyword_calls(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "def __init__(self, pattern_value: pattern | None=None" in source
    assert "def __init__(self, pattern_value: pattern, guard: object" in source
    assert source.count("self.pattern = pattern_value") == 2
    assert "MatchAs(pattern_value=value, name='captured')" in source
    assert "match_case(pattern_value=value, guard=None, body=[])" in source
    ast.parse(source)


def test_positional_calls_remain_unchanged(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(
        SOURCE.replace(
            "MatchAs(pattern=value, name='captured')",
            "MatchAs(value, 'captured')",
        ).replace(
            "match_case(pattern=value, guard=None, body=[])",
            "match_case(value, None, [])",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0
    source = path.read_text(encoding="utf-8")
    assert "MatchAs(value, 'captured')" in source
    assert "match_case(value, None, [])" in source


def test_fails_closed_when_pattern_class_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(SOURCE.replace("class match_case:", "class missing_case:"), encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "missing" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing pattern constructor")
