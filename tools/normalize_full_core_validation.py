"""Remove host-only assumptions from the native full-core probe."""
from __future__ import annotations

from pathlib import Path


BYTECODE_PATH = Path("src/portapy/core/bytecode.py")
FRONTEND_PATH = Path("src/portapy/core/frontend.py")
NATIVE_AST_PATH = Path("src/portapy/core/native_ast.py")


def _normalize_opcode_validation() -> None:
    source = BYTECODE_PATH.read_text(encoding="utf-8")
    old = "            if type(instr.op) is not int or instr.op not in _VALID_OPS:"
    new = "            if instr.op not in _VALID_OPS:"
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"expected one opcode host-type check, found {count}")
    BYTECODE_PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("REMOVED HOST OPCODE TYPE IDENTITY", count)


def _select_standalone_parser() -> None:
    if not NATIVE_AST_PATH.is_file():
        raise RuntimeError(f"missing standalone AST parser: {NATIVE_AST_PATH}")
    source = FRONTEND_PATH.read_text(encoding="utf-8")
    old = "import ast\n"
    new = "from . import native_ast as ast\n"
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"expected one CPython ast import, found {count}")
    FRONTEND_PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("SELECTED STANDALONE NATIVE AST", count)


def main() -> int:
    _normalize_opcode_validation()
    _select_standalone_parser()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
