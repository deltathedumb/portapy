"""Run typed truthiness normalization and repair compiler-sensitive spelling."""
from __future__ import annotations

from pathlib import Path

from tools.normalize_full_core_truthiness_complete import main as normalize_truthiness


VM_PATH = Path("src/portapy/core/vm.py")


def main() -> int:
    normalize_truthiness()

    source = VM_PATH.read_text(encoding="utf-8")
    old = "                    frame.stack[-1], frame.stack[-2] = (frame.stack[-2], frame.stack[-1])"
    new = (
        "                    swap_value = frame.stack[-1]\n"
        "                    frame.stack[-1] = frame.stack[-2]\n"
        "                    frame.stack[-2] = swap_value"
    )
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"native compiler-safe SWAP normalization expected 1 match, found {count}"
        )
    source = source.replace(old, new, 1)
    VM_PATH.write_text(source, encoding="utf-8")

    if "frame.stack[-1], frame.stack[-2] =" in source:
        raise RuntimeError("native subscript tuple assignment survived SWAP normalization")
    print("NORMALIZED COMPILER-SAFE NATIVE SWAP", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
