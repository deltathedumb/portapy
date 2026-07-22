from __future__ import annotations

import inspect

from tools import normalize_full_core_validation as validation


def test_match_defaults_precede_constructor_collision_renames() -> None:
    source = inspect.getsource(validation.main)

    extended = source.index('(\"extended_semantics\"')
    expr_stmt = source.index('(\"expr_stmt_initializer\"')
    pattern_collision = source.index('(\"pattern_constructor_collisions\"')
    node_fields = source.index('(\"native_node_fields\"')

    assert extended < expr_stmt < pattern_collision < node_fields
