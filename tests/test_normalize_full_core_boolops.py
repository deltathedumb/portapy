from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_boolops as normalizer


def test_rewrites_only_boolop_operands_to_dynamic_getattr(
    tmp_path: Path, monkeypatch,
) -> None:
    source = tmp_path / "native_ast.py"
    source.write_text(
        '''def _convert_expr(node, lifted):
    if isinstance(node, A.BinOp):
        return BinOp(_convert_expr(node.left, lifted), node.op, _convert_expr(node.right, lifted))
    if isinstance(node, A.BoolOp):
        return BoolOp(
            And() if node.op == "and" else Or(),
            [_convert_expr(node.left, lifted), _convert_expr(node.right, lifted)],
        )
    raise RuntimeError("unsupported")
''',
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", source)

    assert normalizer.main() == 0

    module = ast.parse(source.read_text(encoding="utf-8"))
    text = ast.unparse(module)
    assert "_convert_expr(getattr(node, 'left'), lifted)" in text
    assert "_convert_expr(getattr(node, 'right'), lifted)" in text
    # The already-working BinOp path remains direct/static.
    assert "_convert_expr(node.left, lifted), node.op" in text


def test_fails_closed_without_exact_boolop_shape(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "native_ast.py"
    source.write_text(
        '''def _convert_expr(node, lifted):
    return node
''',
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", source)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "expected 2 fields" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing BoolOp path")
