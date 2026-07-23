from __future__ import annotations

import ast
from pathlib import Path

from tools.normalize_full_core_builtin_parameter_collisions import normalize_tree


SOURCE = '''class ExceptHandler:
    def __init__(self, type, name, body):
        self.type = type
        self.name = name
        self.body = body

class Subscript:
    def __init__(self, value, slice, ctx=None):
        self.value = value
        self.slice = slice
        self.ctx = ctx

def build(value, index):
    handler = ExceptHandler(type=value, name=None, body=[])
    subscript = Subscript(value=value, slice=index, ctx=None)
    return handler, subscript
'''


def test_repairs_all_builtin_parameters(tmp_path: Path) -> None:
    root = tmp_path / "portapy"
    root.mkdir()
    module = root / "module.py"
    module.write_text(SOURCE, encoding="utf-8")

    constructors, calls, files = normalize_tree(root)

    assert (constructors, calls, files) == (2, 2, 1)
    source = module.read_text(encoding="utf-8")
    assert "def __init__(self, type_value, name, body):" in source
    assert "self.type = type_value" in source
    assert "ExceptHandler(type_value=value, name=None, body=[])" in source
    assert "def __init__(self, value, slice_value, ctx=None):" in source
    assert "self.slice = slice_value" in source
    assert "Subscript(value=value, slice_value=index, ctx=None)" in source
    ast.parse(source)


def test_positional_calls_remain_unchanged(tmp_path: Path) -> None:
    root = tmp_path / "portapy"
    root.mkdir()
    module = root / "module.py"
    module.write_text(
        SOURCE.replace(
            "ExceptHandler(type=value, name=None, body=[])",
            "ExceptHandler(value, None, [])",
        ).replace(
            "Subscript(value=value, slice=index, ctx=None)",
            "Subscript(value, index, None)",
        ),
        encoding="utf-8",
    )

    constructors, calls, files = normalize_tree(root)

    assert (constructors, calls, files) == (2, 0, 1)
    source = module.read_text(encoding="utf-8")
    assert "ExceptHandler(value, None, [])" in source
    assert "Subscript(value, index, None)" in source
    assert "self.type = type_value" in source
    assert "self.slice = slice_value" in source
