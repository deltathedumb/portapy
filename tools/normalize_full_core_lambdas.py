"""Remove variadic lambda shims from the full-core CI probe source."""
from __future__ import annotations

from pathlib import Path
import re


VM_PATH = Path("src/portapy/core/vm.py")


def main() -> int:
    source = VM_PATH.read_text(encoding="utf-8")
    source, count = re.subn(
        r"return\s+lambda\s+\*args\s*,\s*\*\*kwargs\s*:[^\n]*",
        "return _full_core_probe_noop",
        source,
    )
    if count == 0:
        print("NO VARIADIC LAMBDA SHIMS REMAIN")
    else:
        print("REPLACED VARIADIC LAMBDAS", count)
    VM_PATH.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
