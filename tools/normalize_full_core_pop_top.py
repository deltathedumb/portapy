"""Keep the POP_TOP list mutation visible to the native compiler.

The pinned compiler mislowers a method call whose result is immediately
ignored inside the VM dispatch loop.  Every assigned ``frame.stack.pop()``
path works natively, while the lone bare POP_TOP call crashes.  Bind the
removed value to a local so the list mutation is emitted normally; the local
is intentionally unused after the assignment.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")

_OLD = '''                elif op is Op.POP_TOP:
                    frame.stack.pop()
'''
_NEW = '''                elif op is Op.POP_TOP:
                    discarded = frame.stack.pop()
'''


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    count = source.count(_OLD)
    if count != 1:
        raise RuntimeError(
            f"native POP_TOP normalization expected one handler, found {count}"
        )
    source = source.replace(_OLD, _NEW, 1)
    PATH.write_text(source, encoding="utf-8")

    if source.count("discarded = frame.stack.pop()") != 1:
        raise RuntimeError("native POP_TOP validation did not preserve assigned pop")
    if _OLD in source:
        raise RuntimeError("native POP_TOP bare pop remains after normalization")
    print("NORMALIZED NATIVE POP_TOP", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
