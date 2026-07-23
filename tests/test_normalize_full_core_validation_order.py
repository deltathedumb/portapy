from __future__ import annotations

from pathlib import Path


VALIDATION = (
    Path(__file__).parents[1] / "tools" / "normalize_full_core_validation.py"
)


def test_match_defaults_precede_constructor_collision_renames() -> None:
    source = VALIDATION.read_text(encoding="utf-8")

    extended = source.index('("extended_semantics"')
    expr_stmt = source.index('("expr_stmt_initializer"')
    pattern_collision = source.index('("pattern_constructor_collisions"')
    node_fields = source.index('("native_node_fields"')

    assert extended < expr_stmt < pattern_collision < node_fields


def test_typed_container_access_follows_reference_data_access() -> None:
    source = VALIDATION.read_text(encoding="utf-8")

    data_access = source.index('("reference_data_access"')
    container_access = source.index('("reference_container_access"')
    handle_kind_access = source.index('("reference_handle_kind_access"')

    assert data_access < container_access < handle_kind_access
