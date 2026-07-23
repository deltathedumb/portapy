from __future__ import annotations

import ast

from tools import normalize_full_core_native_statement_bodies as normalizer


def test_control_flow_bodies_are_loaded_and_converted_before_construction() -> None:
    module = ast.parse(
        '''
def _convert_stmt(node: object, lifted: dict):
    if isinstance(node, _npr_ast_nodes_For):
        return For(target, iterator, _convert_body(node.body, lifted), _convert_body(node.orelse, lifted))
    return None
'''
    )
    function = normalizer._convert_stmt(module)

    assert normalizer._normalize_function(function) == 2

    ast.fix_missing_locations(module)
    source = ast.unparse(module)
    assert "_native_for_body_body: list[object] = getattr(node, 'body')" in source
    assert "_native_for_orelse_body: list[object] = getattr(node, 'orelse')" in source
    assert "_native_converted_for_body_body: list[stmt] = _convert_body(" in source
    assert "_native_converted_for_orelse_body: list[stmt] = _convert_body(" in source
    assert "_convert_body(node.body" not in source
    assert "_convert_body(node.orelse" not in source
    assert "For(target, iterator, _native_converted_for_body_body, _native_converted_for_orelse_body)" in source
