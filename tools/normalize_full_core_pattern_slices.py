"""Expand the VM's dynamic starred-pattern slice for native compilation."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    old = (
        "                    matched, nested = self._match_pattern(frame, "
        "list(value[star:len(value) - (len(patterns) - star - 1)]), pattern[1])"
    )
    new = (
        "                    matched, nested = self._match_pattern(\n"
        "                        frame,\n"
        "                        _full_core_probe_copy_range(\n"
        "                            value,\n"
        "                            star,\n"
        "                            len(value) - (len(patterns) - star - 1),\n"
        "                        ),\n"
        "                        pattern[1],\n"
        "                    )"
    )
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected one starred-pattern slice, found {count}"
        )
    PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("EXPANDED STARRED PATTERN SLICE", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
