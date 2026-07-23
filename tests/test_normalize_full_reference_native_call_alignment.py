from __future__ import annotations

import ast

from tools import normalize_full_reference_safe_host_ids as normalizer


def test_legacy_value_lookup_uses_native_slot_accessor() -> None:
    module = ast.parse(
        '''
def replace_value(instance, handle, value):
    slot = instance._values.get(handle)
    slot.value = value
'''
    )
    rewrite = normalizer._LegacyValueLookupRewriter()
    module = rewrite.visit(module)
    ast.fix_missing_locations(module)
    source = ast.unparse(module)

    assert rewrite.replaced == 1
    assert "slot = instance._value_slot(handle)" in source
    assert "instance._values.get(handle)" not in source


def test_nested_slot_value_calls_are_hoisted_before_container_writes() -> None:
    module = ast.parse(
        '''
def assign_item(instance, item, values, index):
    values[index] = _slot_value(instance, item)


def append_item(instance, item, values):
    values.append(_slot_value(instance, item))
'''
    )
    hoister = normalizer._NestedSlotValueHoister()
    module = hoister.visit(module)
    ast.fix_missing_locations(module)
    source = ast.unparse(module)

    assert hoister.hoisted == 2
    assert "values[index] = _slot_value(" not in source
    assert "values.append(_slot_value(" not in source
    assert "_native_slot_value_0 = _slot_value(instance, item)" in source
    assert "values[index] = _native_slot_value_0" in source
    assert "_native_slot_value_1 = _slot_value(instance, item)" in source
    assert "values.append(_native_slot_value_1)" in source
