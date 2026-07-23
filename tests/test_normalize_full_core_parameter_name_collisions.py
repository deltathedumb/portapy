from __future__ import annotations

import ast
from pathlib import Path

from tools.normalize_full_core_parameter_name_collisions import normalize_tree


def test_repairs_explicit_and_generated_parameter_collisions(
    tmp_path: Path,
) -> None:
    root = tmp_path / "portapy"
    root.mkdir()
    module = root / "module.py"
    module.write_text(
        '''from dataclasses import dataclass, field

class alias:
    pass

class arguments:
    pass

@dataclass
class ImportNode:
    module: str
    alias: str | None = None
    pos: object = field(default_factory=lambda: NO_POS)

def dispatch(arguments):
    return arguments

def build(value):
    return ImportNode(module='demo', alias=value)
''',
        encoding="utf-8",
    )

    explicit, generated, classes, calls = normalize_tree(root)

    assert (explicit, generated, classes, calls) == (1, 1, 1, 1)
    source = module.read_text(encoding="utf-8")
    assert "def dispatch(__portapy_param_arguments):" in source
    assert "return __portapy_param_arguments" in source
    assert "def __init__(self, module: str, __portapy_param_alias: str | None=None" in source
    assert "self.alias = __portapy_param_alias" in source
    assert "pos: object=NO_POS" in source
    assert "ImportNode(module='demo', __portapy_param_alias=value)" in source
    ast.parse(source)


def test_preserves_positional_calls_and_noncolliding_parameters(
    tmp_path: Path,
) -> None:
    root = tmp_path / "portapy"
    root.mkdir()
    module = root / "module.py"
    module.write_text(
        '''class keyword:
    pass

def lookup(keyword, fallback):
    return keyword or fallback

def run(value):
    return lookup(value, None)
''',
        encoding="utf-8",
    )

    explicit, generated, classes, calls = normalize_tree(root)

    assert (explicit, generated, classes, calls) == (1, 0, 0, 0)
    source = module.read_text(encoding="utf-8")
    assert "def lookup(__portapy_param_keyword, fallback):" in source
    assert "return __portapy_param_keyword or fallback" in source
    assert "lookup(value, None)" in source


def test_rejects_mutable_default_factories_for_colliding_fields(
    tmp_path: Path,
) -> None:
    root = tmp_path / "portapy"
    root.mkdir()
    (root / "module.py").write_text(
        '''from dataclasses import dataclass, field

class values:
    pass

@dataclass
class Node:
    values: list = field(default_factory=list)
''',
        encoding="utf-8",
    )

    try:
        normalize_tree(root)
    except RuntimeError as error:
        assert "unsupported non-lambda default factory" in str(error)
    else:
        raise AssertionError("mutable generated default was accepted")
