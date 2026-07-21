"""Restore concrete tuple and set construction in the native full VM."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    old = '''                elif op in (Op.BUILD_TUPLE, Op.BUILD_SET):
                    if len(frame.stack) < instr.arg:
                        _raise_typed("RuntimeError: collection stack underflow")
                    values = _full_core_probe_pop_tail(frame.stack, instr.arg)
                    frame.stack.append(None)
'''
    new = '''                elif op in (Op.BUILD_TUPLE, Op.BUILD_SET):
                    if len(frame.stack) < instr.arg:
                        _raise_typed("RuntimeError: collection stack underflow")
                    values = _full_core_probe_pop_tail(frame.stack, instr.arg)
                    if op is Op.BUILD_TUPLE:
                        frame.stack.append(tuple(values))
                    else:
                        frame.stack.append(set(values))
'''
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"native tuple/set bootstrap: expected 1 match, found {count}"
        )
    PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("RESTORED NATIVE TUPLE AND SET CONSTRUCTION", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
