"""Apply the complete native full-core normalization pipeline."""
from __future__ import annotations

from pathlib import Path

from tools.combine_full_core_native_parser import main as combine_native_parser
from tools.materialize_full_reference_entry import main as materialize_reference_entry
from tools.normalize_full_core_boolops import main as normalize_boolops
from tools.normalize_full_core_builtins import main as normalize_builtins
from tools.normalize_full_core_calls_closures import (
    main as normalize_calls_closures,
)
from tools.normalize_full_core_closures import main as normalize_closures
from tools.normalize_full_core_collections import main as normalize_collections
from tools.normalize_full_core_extended_semantics_compat import (
    main as normalize_extended_semantics,
)
from tools.normalize_full_core_keyword_calls import (
    main as normalize_keyword_calls,
)
from tools.normalize_full_core_lambdas import main as normalize_lambdas
from tools.normalize_full_core_make_function import main as normalize_make_function
from tools.normalize_full_core_native_parser import main as normalize_native_parser
from tools.normalize_full_core_native_semantics import main as normalize_native_semantics
from tools.normalize_full_core_opcode_maps import main as normalize_opcode_maps
from tools.normalize_full_core_pattern_slices import main as normalize_pattern_slices
from tools.normalize_full_core_pop_top import main as normalize_pop_top
from tools.normalize_full_core_probe import main as normalize_probe
from tools.normalize_full_core_tracebacks import main as normalize_tracebacks
from tools.normalize_full_core_truthiness_directives import main as normalize_truthiness
from tools.normalize_full_reference_abi_helpers import (
    main as normalize_reference_abi_helpers,
)
from tools.normalize_full_reference_bytes_literals import (
    main as normalize_reference_bytes_literals,
)
from tools.normalize_full_reference_data_access import (
    main as normalize_reference_data_access,
)
from tools.normalize_full_reference_data_builders import (
    main as normalize_reference_data_builders,
)
from tools.normalize_full_reference_error_locations import (
    main as normalize_reference_error_locations,
)
from tools.normalize_full_reference_error_text import (
    main as normalize_reference_error_text,
)
from tools.normalize_full_reference_errors import (
    main as normalize_reference_errors,
)
from tools.normalize_full_reference_expression_kinds import (
    main as normalize_reference_expression_kinds,
)
from tools.normalize_full_reference_float_bits import (
    main as normalize_reference_float_bits,
)
from tools.normalize_full_reference_nested_kinds import (
    main as normalize_reference_nested_kinds,
)
from tools.normalize_full_reference_runtime import (
    main as normalize_reference_runtime,
)
from tools.normalize_full_reference_source_preprocess import (
    main as normalize_reference_source_preprocess,
)
from tools.normalize_full_reference_value_kinds import (
    main as normalize_reference_value_kinds,
)


BYTECODE_PATH = Path("src/portapy/core/bytecode.py")


def _normalize_nested_code_introspection() -> None:
    source = BYTECODE_PATH.read_text(encoding="utf-8")
    old = '''def _unwrap_nested_code(item: object) -> object:
    if isinstance(item, tuple) and len(item) in (2, 3) and isinstance(item[0], CodeObject):
        return item[0]
    if isinstance(item, tuple) and len(item) in (3, 4) and isinstance(item[1], CodeObject):
        return item[1]
    return item
'''
    new = '''def _unwrap_nested_code(item: object) -> object:
    return item
'''
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected one nested-code introspection helper, found {count}"
        )
    BYTECODE_PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("DISABLED HOST-ONLY NESTED CODE INTROSPECTION", count)


def _normalize_opcode_validation() -> None:
    source = BYTECODE_PATH.read_text(encoding="utf-8")
    old = "            if type(instr.op) is not int or instr.op not in _VALID_OPS:"
    new = "            if instr.op not in _VALID_OPS:"
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"expected one opcode host-type check, found {count}")
    BYTECODE_PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("REMOVED HOST OPCODE TYPE IDENTITY", count)


def main() -> int:
    # These passes prepare the source modules imported by the generated entry.
    normalize_probe()
    normalize_lambdas()
    normalize_native_semantics()
    normalize_opcode_maps()
    normalize_reference_runtime()

    materialize_reference_entry()
    normalize_reference_abi_helpers()
    normalize_reference_float_bits()
    normalize_reference_errors()
    normalize_reference_error_text()
    normalize_reference_error_locations()
    normalize_reference_value_kinds()
    normalize_reference_expression_kinds()
    normalize_reference_nested_kinds()
    normalize_reference_source_preprocess()
    normalize_reference_data_builders()
    normalize_reference_data_access()
    normalize_reference_bytes_literals()
    normalize_native_parser()
    normalize_calls_closures()
    normalize_keyword_calls()
    combine_native_parser()
    normalize_boolops()
    normalize_closures()
    normalize_pattern_slices()
    normalize_extended_semantics()
    normalize_pop_top()
    normalize_make_function()
    normalize_collections()
    normalize_builtins()
    normalize_tracebacks()
    _normalize_nested_code_introspection()
    _normalize_opcode_validation()
    normalize_truthiness()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
