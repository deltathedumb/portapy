from __future__ import annotations

import ast
from pathlib import Path

from tools.normalize_full_core_builtin_parameter_collisions import normalize_tree


SOURCE = '''class ExceptHandler:
    def __init__(self, type, name, body):
        self.type = type
        self.name = name
        self.body = body

def build(value):
    return ExceptHandler(type=value, name=None, body=[])
'''


def test_repairs_except_handler_type_parameter(
    tmp_path: Path,
) -> None:
    root = tmp_path / "portapy"
    root.mkdir()
    module = root / "module.py"
    module.write_text(SOURCE, encoding="utf-8")

    constructors, calls, files = normalize_tree(root)

    assert (constructors, calls, files) == (1, 1, 1)
    source = module.read_text(encoding="utf-8")
    assert "def __init__(self, type_value, name, body):" in source
    assert "self.type = type_value" in source
    assert "ExceptHandler(type_value=value, name=None, body=[])" in source
    ast.parse(source)


def test_positional_except_handler_calls_remain_unchanged(
    tmp_path: Path,
) -> None:
    root = tmp_path / "portapy"
    root.mkdir()
    module = root / "module.py"
    module.write_text(
        SOURCE.replace(
            "ExceptHandler(type=value, name=None, body=[])",
            "ExceptHandler(value, None, [])",
        ),
        encoding="utf-8",
    )

    constructors, calls, files = normalize_tree(root)

    assert (constructors, calls, files) == (1, 0, 1)
    source = module.read_text(encoding="utf-8")
    assert "ExceptHandler(value, None, [])" in source
    assert "self.type = type_value" in source
