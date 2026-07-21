"""Restore concrete tuple and set construction in the native full VM."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")

_CANONICAL_BOOTSTRAP = '''                elif op in (Op.BUILD_TUPLE, Op.BUILD_SET):
                    if len(frame.stack) < instr.arg:
                        _raise_typed("RuntimeError: collection stack underflow")
                    values = _full_core_probe_pop_tail(frame.stack, instr.arg)
                    frame.stack.append(None)
'''

_COMPACT_BOOTSTRAP = '''                elif op in (Op.BUILD_TUPLE, Op.BUILD_SET):
                    if len(frame.stack) < instr.arg: _raise_typed("RuntimeError: collection stack underflow")
                    values = _full_core_probe_pop_tail(frame.stack, instr.arg)
                    frame.stack.append(None)
'''

_RESTORED = '''                elif op in (Op.BUILD_TUPLE, Op.BUILD_SET):
                    if len(frame.stack) < instr.arg:
                        _raise_typed("RuntimeError: collection stack underflow")
                    values = _full_core_probe_pop_tail(frame.stack, instr.arg)
                    if op is Op.BUILD_TUPLE:
                        frame.stack.append(tuple(values))
                    else:
                        frame.stack.append(set(values))
'''


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    matches = [
        candidate
        for candidate in (_CANONICAL_BOOTSTRAP, _COMPACT_BOOTSTRAP)
        if source.count(candidate) == 1
    ]
    if len(matches) != 1:
        counts = {
            "canonical": source.count(_CANONICAL_BOOTSTRAP),
            "compact": source.count(_COMPACT_BOOTSTRAP),
        }
        raise RuntimeError(
            "native tuple/set bootstrap: expected one verified source form, "
            f"found {counts}"
        )
    source = source.replace(matches[0], _RESTORED, 1)
    PATH.write_text(source, encoding="utf-8")
    print("RESTORED NATIVE TUPLE AND SET CONSTRUCTION", 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
