"""Replace exception-driven frontend name lookup with a native-safe loop.

The native compiler leaves the caught ValueError in its global exception state
when ``list.index`` misses.  `_Lowerer.name_index` then returns a valid index,
but the surrounding source execution is still reported as a type error.  An
explicit loop has the same deduplication semantics without raising.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/frontend.py")

_OLD = '''    def name_index(self, value: str) -> int:
        try:
            return self.names.index(value)
        except ValueError:
            self.names.append(value)
            return len(self.names) - 1
'''

_NEW = '''    def name_index(self, value: str) -> int:
        index = 0
        while index < len(self.names):
            if self.names[index] == value:
                return index
            index += 1
        self.names.append(value)
        return len(self.names) - 1
'''


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    count = source.count(_OLD)
    if count != 1:
        raise RuntimeError(
            f"native frontend name_index expected one exception lookup, found {count}"
        )
    source = source.replace(_OLD, _NEW, 1)
    PATH.write_text(source, encoding="utf-8")

    if ".names.index(" in source:
        raise RuntimeError("native frontend still contains exception-driven name lookup")
    required = (
        "while index < len(self.names):",
        "if self.names[index] == value:",
        "self.names.append(value)",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(f"native frontend name_index validation failed: {missing}")
    print("NORMALIZED NATIVE FRONTEND NAME INDEX", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
