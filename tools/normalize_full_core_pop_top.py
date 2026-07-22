"""Lower native POP_TOP uses through inline STORE_NAME/DELETE_NAME ops.

The pinned native compiler crashes in the VM's standalone POP_TOP dispatch.
A helper method that emitted the replacement instructions was also miscompiled
when the frontend itself ran natively. Inline the two already-stable bytecode
emissions at every discard site, using PortaPy's reserved internal namespace.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/frontend.py")
_EXPECTED_EMISSIONS = 5

_OLD_EMISSION = "self.emit(Op.POP_TOP)"
_NEW_EMISSION = '''self.emit(
                    Op.STORE_NAME,
                    self.name_index("__pyinbin_internal_discard"),
                )
                self.emit(
                    Op.DELETE_NAME,
                    self.name_index("__pyinbin_internal_discard"),
                )'''


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
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
    if source.count('self.name_index("__pyinbin_internal_discard")') != (
        _EXPECTED_EMISSIONS * 2
    ):
        raise RuntimeError("native inline discard names were not installed everywhere")
    if source.count("Op.STORE_NAME,") < _EXPECTED_EMISSIONS:
        raise RuntimeError("native inline discard stores are missing")
    if source.count("Op.DELETE_NAME,") < _EXPECTED_EMISSIONS:
        raise RuntimeError("native inline discard deletes are missing")

    print("NORMALIZED INLINE NATIVE POP_TOP EMISSIONS", emission_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
