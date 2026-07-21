"""Remove host-type identity checks invalid in the native object model."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/bytecode.py")


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    old = "            if type(instr.op) is not int or instr.op not in _VALID_OPS:"
    new = "            if instr.op not in _VALID_OPS:"
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"expected one opcode host-type check, found {count}")
    PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("REMOVED HOST OPCODE TYPE IDENTITY", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
