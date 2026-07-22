from __future__ import annotations

import ast
from pathlib import Path

from tools.normalize_full_core_local_name_collisions import normalize_tree


def test_renames_nonparameter_locals_across_flattened_modules(
    tmp_path: Path,
) -> None:
    root = tmp_path / "portapy"
    root.mkdir()
    (root / "classes.py").write_text(
        "class keyword:\n    pass\n\nclass expr:\n    pass\n",
        encoding="utf-8",
    )
    module = root / "runtime.py"
    module.write_text(
        '''def lower(items):
    values = []
    for keyword in items:
        expr = keyword.value
        values.append(expr)
    return values
''',
        encoding="utf-8",
    )

    renamed, functions, files = normalize_tree(root)

    assert (renamed, functions, files) == (2, 1, 1)
    source = module.read_text(encoding="utf-8")
    assert "for __portapy_local_keyword in items:" in source
    assert "__portapy_local_expr = __portapy_local_keyword.value" in source
    assert "values.append(__portapy_local_expr)" in source
    ast.parse(source)


def test_leaves_colliding_parameters_for_parameter_specific_passes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "portapy"
    root.mkdir()
    (root / "module.py").write_text(
        '''class keyword:
    pass

def lookup(keyword):
    return keyword
''',
        encoding="utf-8",
    )

    renamed, functions, files = normalize_tree(root)

    assert (renamed, functions, files) == (0, 0, 0)
    source = (root / "module.py").read_text(encoding="utf-8")
    assert "def lookup(keyword):" in source
    assert "return keyword" in source


def test_processes_nested_scopes_independently(tmp_path: Path) -> None:
    root = tmp_path / "portapy"
    root.mkdir()
    module = root / "module.py"
    module.write_text(
        '''class expr:
    pass

def outer(values):
    expr = values[0]
    def inner(values):
        expr = values[1]
        return expr
    return expr, inner(values)
''',
        encoding="utf-8",
    )

    renamed, functions, files = normalize_tree(root)

    assert (renamed, functions, files) == (2, 2, 1)
    source = module.read_text(encoding="utf-8")
    assert source.count("__portapy_local_expr") == 4
    ast.parse(source)
