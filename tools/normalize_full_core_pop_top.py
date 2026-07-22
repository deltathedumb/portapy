"""Lower POP_TOP without the pinned compiler's crashing list-pop call.

The generic VM can use ``frame.stack.pop()``, but that method call crashes when
it appears as the standalone POP_TOP operation in a native build. Other VM paths
already exercise list slicing successfully, so replace the stack with every item
except its final element. This preserves the exact stack effect without calling
``pop`` at all.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")

_OLD = '''                elif op is Op.POP_TOP:
                    frame.stack.pop()
'''
_NEW = '''                elif op is Op.POP_TOP:
                    frame.stack = frame.stack[:-1]
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

    if source.count("frame.stack = frame.stack[:-1]") != 1:
        raise RuntimeError("native POP_TOP validation lost slice-based stack shrink")
    if _OLD in source:
        raise RuntimeError("native POP_TOP bare pop remains after normalization")
    print("NORMALIZED NATIVE POP_TOP", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
