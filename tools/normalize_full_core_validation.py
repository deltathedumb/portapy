"""Apply final validation-oriented rewrites to the native full-core probe."""
from __future__ import annotations

from pathlib import Path

from tools.combine_full_core_native_parser import main as combine_native_parser
from tools.materialize_full_reference_entry import main as materialize_reference_entry
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
from tools.normalize_full_core_native_parser import main as normalize_native_parser
from tools.normalize_full_core_pattern_slices import main as normalize_pattern_slices
from tools.normalize_full_reference_abi_helpers import (
    main as normalize_reference_abi_helpers,
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
    materialize_reference_entry()
    normalize_reference_abi_helpers()
    normalize_native_parser()
    normalize_calls_closures()
    normalize_keyword_calls()
    combine_native_parser()
    normalize_closures()
    normalize_pattern_slices()
    normalize_extended_semantics()
    normalize_collections()
    normalize_builtins()
    _normalize_nested_code_introspection()
    _normalize_opcode_validation()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
