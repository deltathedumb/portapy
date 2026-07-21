"""Apply final validation-oriented rewrites to the native full-core probe."""
from __future__ import annotations

from pathlib import Path

from tools.normalize_full_core_calls_closures import (
    main as normalize_calls_closures,
)
from tools.normalize_full_core_collections import (
    main as normalize_collections,
)
from tools.normalize_full_core_extended_semantics import (
    main as normalize_extended_semantics,
)
from tools.normalize_full_core_native_parser import main as normalize_native_parser
from tools.normalize_full_core_pattern_slices import main as normalize_pattern_slices


BYTECODE_PATH = Path("src/portapy/core/bytecode.py")


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
    normalize_native_parser()
    normalize_pattern_slices()
    normalize_extended_semantics()
    normalize_calls_closures()
    normalize_collections()
    _normalize_opcode_validation()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
