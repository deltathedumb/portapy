"""Lower native POP_TOP uses through inline STORE_NAME/DELETE_NAME ops.

The pinned native compiler crashes in the VM's standalone POP_TOP dispatch.
A helper method that emitted the replacement instructions was also miscompiled
when the frontend itself ran natively. Inline the two already-stable bytecode
emissions at every discard site, preserving each site's nesting indentation and
using PortaPy's reserved internal namespace.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/frontend.py")
_EXPECTED_EMISSIONS = 5
_OLD_EMISSION = "self.emit(Op.POP_TOP)"
_INTERNAL_NAME = "__pyinbin_internal_discard"


def _replacement_lines(indent: str) -> list[str]:
    return [
        f"{indent}self.emit(",
        f"{indent}    Op.STORE_NAME,",
        f'{indent}    self.name_index("{_INTERNAL_NAME}"),',
        f"{indent})",
        f"{indent}self.emit(",
        f"{indent}    Op.DELETE_NAME,",
        f'{indent}    self.name_index("{_INTERNAL_NAME}"),',
        f"{indent})",
    ]


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    output: list[str] = []
    emission_count = 0
    for line in source.splitlines():
        if line.strip() != _OLD_EMISSION:
            output.append(line)
            continue
        indent = line[: len(line) - len(line.lstrip())]
        output.extend(_replacement_lines(indent))
        emission_count += 1

    if emission_count != _EXPECTED_EMISSIONS:
        raise RuntimeError(
            "native POP_TOP normalization expected "
            f"{_EXPECTED_EMISSIONS} emissions, found {emission_count}"
        )

    normalized = "\n".join(output) + ("\n" if source.endswith("\n") else "")
    PATH.write_text(normalized, encoding="utf-8")

    if _OLD_EMISSION in normalized:
        raise RuntimeError("native POP_TOP emission remains after normalization")
    expected_names = _EXPECTED_EMISSIONS * 2
    marker = f'self.name_index("{_INTERNAL_NAME}")'
    if normalized.count(marker) != expected_names:
        raise RuntimeError("native inline discard names were not installed everywhere")
    if normalized.count("Op.STORE_NAME,") < _EXPECTED_EMISSIONS:
        raise RuntimeError("native inline discard stores are missing")
    if normalized.count("Op.DELETE_NAME,") < _EXPECTED_EMISSIONS:
        raise RuntimeError("native inline discard deletes are missing")

    print("NORMALIZED INLINE NATIVE POP_TOP EMISSIONS", emission_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
