"""Restore concrete tuple and set construction in the native full VM."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")

_BLOCK_START = "                elif op in (Op.BUILD_TUPLE, Op.BUILD_SET):\n"
_BLOCK_END = "                elif op is Op.GET_ITEM:\n"
_BOOTSTRAP_VALUE = "                    frame.stack.append(None)"
_RESTORED_VALUE = '''                    if op is Op.BUILD_TUPLE:
                        frame.stack.append(tuple(values))
                    else:
                        frame.stack.append(set(values))'''

_CANONICAL_BOOTSTRAP = '''                elif op in (Op.BUILD_TUPLE, Op.BUILD_SET):
                    if len(frame.stack) < instr.arg:
                        _raise_typed("RuntimeError: collection stack underflow")
                    values = _full_core_probe_pop_tail(frame.stack, instr.arg)
                    frame.stack.append(None)
                elif op is Op.GET_ITEM:
'''

_COMPACT_BOOTSTRAP = '''                elif op in (Op.BUILD_TUPLE, Op.BUILD_SET):
                    if len(frame.stack) < instr.arg: _raise_typed("RuntimeError: collection stack underflow")
                    values = frame.stack[-instr.arg:] if instr.arg else []
                    if instr.arg: del frame.stack[-instr.arg:]
                    frame.stack.append(None)
                elif op is Op.GET_ITEM:
'''


def _collection_block(source: str) -> tuple[int, int, str]:
    if source.count(_BLOCK_START) != 1:
        raise RuntimeError(
            "native tuple/set bootstrap: expected one BUILD_TUPLE/BUILD_SET block"
        )
    start = source.find(_BLOCK_START)
    end = source.find(_BLOCK_END, start + len(_BLOCK_START))
    if end < 0:
        raise RuntimeError("native tuple/set bootstrap: GET_ITEM boundary not found")
    block = source[start:end]
    if "collection stack underflow" not in block or "values =" not in block:
        raise RuntimeError("native tuple/set bootstrap: required safety checks are missing")
    if block.count(_BOOTSTRAP_VALUE) != 1:
        raise RuntimeError(
            "native tuple/set bootstrap: expected one placeholder collection result"
        )
    if "tuple(values)" in block or "set(values)" in block:
        raise RuntimeError("native tuple/set bootstrap: block is already partially restored")
    return start, end, block


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    start, end, block = _collection_block(source)
    restored = block.replace(_BOOTSTRAP_VALUE, _RESTORED_VALUE, 1)
    PATH.write_text(source[:start] + restored + source[end:], encoding="utf-8")
    print("RESTORED NATIVE TUPLE AND SET CONSTRUCTION", 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
