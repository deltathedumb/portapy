"""Update the legacy native function host for the keyword-variadic milestone."""
from __future__ import annotations

from pathlib import Path


HOST = Path("tests/native_function_host.c")
OLD = 'def bad(**kwargs):\\n    return 1\\n'
NEW = 'def bad(**):\\n    return 1\\n'


def main() -> int:
    source = HOST.read_text(encoding="utf-8")
    count = source.count(OLD)
    if count != 1:
        raise RuntimeError(f"expected one legacy kwargs rejection fixture, found {count}")
    HOST.write_text(source.replace(OLD, NEW, 1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
