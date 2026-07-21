"""Normalize CPython-valid shorthand unsupported by the pinned asmpython parser.

This tool mutates only the CI checkout used by the full-core transition probe.
Each replacement is exact and fails closed so the probe cannot silently rewrite
unrelated source.
"""
from __future__ import annotations

from pathlib import Path


REPLACEMENTS: dict[str, tuple[tuple[str, str], ...]] = {
    "src/portapy/core/frontend.py": (
        (
            "                    if bound is None: self.emit(Op.LOAD_CONST, self.constant(None))\n"
            "                    else: self.expr(bound)",
            "                    if bound is None:\n"
            "                        self.emit(Op.LOAD_CONST, self.constant(None))\n"
            "                    else:\n"
            "                        self.expr(bound)",
        ),
    ),
    "src/portapy/core/vm.py": (
        (
            "                    right = frame.stack.pop(); left = frame.stack.pop()",
            "                    right = frame.stack.pop()\n"
            "                    left = frame.stack.pop()",
        ),
    ),
}


def normalize(path: Path, replacements: tuple[tuple[str, str], ...]) -> None:
    source = path.read_text(encoding="utf-8")
    for old, new in replacements:
        count = source.count(old)
        if count != 1:
            raise RuntimeError(
                f"expected exactly one normalization target in {path}: {old!r}; found {count}"
            )
        source = source.replace(old, new)
    path.write_text(source, encoding="utf-8")
    print("NORMALIZED", path)


def main() -> int:
    for name, replacements in REPLACEMENTS.items():
        normalize(Path(name), replacements)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
