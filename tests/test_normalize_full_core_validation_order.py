from __future__ import annotations

import inspect

from tools import normalize_full_core_validation as validation


def test_match_defaults_precede_constructor_collision_renames() -> None:
    source = inspect.getsource(validation.main)

    assert source.index('(\"extended_semantics\"') < source.index(
        '(\"expr_stmt_initializer\"'
    )
    assert source.index('(\"expr_stmt_initializer\"') < source.index(
        '(\"native_node_fields\"'
    )
