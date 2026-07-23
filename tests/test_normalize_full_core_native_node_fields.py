from __future__ import annotations

import ast

from tools import normalize_full_core_native_node_fields as normalizer


def test_opaque_node_fields_use_runtime_getattr() -> None:
    module = ast.parse(
        '''
def _convert_stmt(node: object, lifted: dict, other: object):
    if isinstance(node, ExprStmt):
        return Expr(_convert_expr(node.expr, lifted))
    return (node.name, other.value)
'''
    )
    function = module.body[0]
    assert isinstance(function, ast.FunctionDef)

    count, fields = normalizer._normalize_function(function)
    ast.fix_missing_locations(module)
    source = ast.unparse(module)

    assert count == 2
    assert fields == {"expr", "name"}
    assert "node.expr" not in source
    assert "node.name" not in source
    assert "getattr(node, 'expr')" in source
    assert "getattr(node, 'name')" in source
    assert "other.value" in source
