"""Switch the native full-core build from CPython ast to PortaPy's parser bridge."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/frontend.py")


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    old = "import ast\n"
    new = "from . import native_ast as ast\n"
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"expected one frontend ast import, found {count}")
    PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("ENABLED SELF-HOSTED NATIVE PARSER", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
