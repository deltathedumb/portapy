"""Avoid the pinned native compiler's crashing POP_TOP dispatch.

Expression statements still have to be evaluated for side effects, but their
result does not need to be removed before the frame's explicit return. Native
frames may therefore retain these unused values underneath later operands. The
bytecode operations consume only the values they push, and RETURN uses the
explicit top value, so removing this one emission preserves observable Python
semantics while bypassing the broken standalone stack-removal path.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/frontend.py")

_OLD = '''            if not self.interactive and not isinstance(node.value, ast.Yield):
                self.emit(Op.POP_TOP)
'''


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    count = source.count(_OLD)
    if count != 1:
        raise RuntimeError(
            "native expression POP_TOP normalization expected one emission, "
            f"found {count}"
        )
    source = source.replace(_OLD, "", 1)
    PATH.write_text(source, encoding="utf-8")

    if _OLD in source:
        raise RuntimeError("native expression POP_TOP emission remains")
    marker = '''        if isinstance(node, ast.Expr):
            self.expr(node.value)
'''
    if marker not in source:
        raise RuntimeError("native expression evaluation was not preserved")
    print("REMOVED NATIVE EXPRESSION POP_TOP", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
