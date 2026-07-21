"""Enable explicit builtin seeding for the native full-core VM."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    old = '''        namespace = globals_ if globals_ is not None else {}
        namespace.setdefault("__annotations__", {})
        # Module definitions and function globals must share one namespace.'''
    new = '''        namespace = globals_ if globals_ is not None else {}
        namespace.setdefault("__annotations__", {})
        self._seed_builtins(namespace)
        # Module definitions and function globals must share one namespace.'''
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected one VM namespace initialization, found {count}"
        )
    PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("ENABLED EXPLICIT BUILTIN SEEDING", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
