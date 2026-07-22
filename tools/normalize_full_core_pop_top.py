"""Lower native POP_TOP uses through stable STORE_NAME/DELETE_NAME ops.

The pinned native compiler crashes in the VM's standalone POP_TOP dispatch,
regardless of whether that handler calls ``pop`` or uses slicing. STORE_NAME's
stack pop is already exercised successfully throughout the runtime, so emit a
short-lived internal binding for every discard and immediately delete it. The
internal name contains characters that cannot occur in a Python identifier,
preventing collisions with user code.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/frontend.py")
_EXPECTED_EMISSIONS = 5

_HELPER_ANCHOR = '''        return len(self.instructions) - 1

    def patch(self, offset: int, target: int) -> None:
'''
_HELPER_REPLACEMENT = '''        return len(self.instructions) - 1

    def discard_top(self) -> None:
        discard_name = f"<discard:{len(self.instructions)}>"
        discard_index = self.name_index(discard_name)
        self.emit(Op.STORE_NAME, discard_index)
        self.emit(Op.DELETE_NAME, discard_index)

    def patch(self, offset: int, target: int) -> None:
'''
_OLD_EMISSION = "self.emit(Op.POP_TOP)"
_NEW_EMISSION = "self.discard_top()"


def main() -> int:
    source = PATH.read_text(encoding="utf-8")

    anchor_count = source.count(_HELPER_ANCHOR)
    if anchor_count != 1:
        raise RuntimeError(
            "native discard helper insertion expected one anchor, "
            f"found {anchor_count}"
        )
    source = source.replace(_HELPER_ANCHOR, _HELPER_REPLACEMENT, 1)

    emission_count = source.count(_OLD_EMISSION)
    if emission_count != _EXPECTED_EMISSIONS:
        raise RuntimeError(
            "native POP_TOP normalization expected "
            f"{_EXPECTED_EMISSIONS} emissions, found {emission_count}"
        )
    source = source.replace(_OLD_EMISSION, _NEW_EMISSION)
    PATH.write_text(source, encoding="utf-8")

    if _OLD_EMISSION in source:
        raise RuntimeError("native POP_TOP emission remains after normalization")
    if source.count(_NEW_EMISSION) != _EXPECTED_EMISSIONS:
        raise RuntimeError("native discard calls were not installed everywhere")
    required = (
        "def discard_top(self) -> None:",
        'discard_name = f"<discard:{len(self.instructions)}>"',
        "self.emit(Op.STORE_NAME, discard_index)",
        "self.emit(Op.DELETE_NAME, discard_index)",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(f"native discard helper validation failed: {missing}")

    print("NORMALIZED NATIVE POP_TOP EMISSIONS", emission_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
