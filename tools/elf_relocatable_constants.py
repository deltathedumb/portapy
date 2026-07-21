"""Move generated relocatable constant tables out of read-only ELF data."""
from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: elf_relocatable_constants.py <assembly>")
    path = Path(sys.argv[1])
    source = path.read_text(encoding="utf-8")
    marker = "section .rodata"
    count = source.count(marker)
    if count != 1:
        raise RuntimeError(f"expected one generated .rodata section, found {count}")
    source = source.replace(marker, "section .data", 1)
    path.write_text(source, encoding="utf-8")
    print("MOVED RELOCATABLE CONSTANTS", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
