"""Keep the POP_TOP list mutation visible to the native compiler.

The pinned compiler can eliminate a list ``pop()`` whose result only lands in an
unused local, turning expression statements into a native crash. Store the
removed value on the VM instance instead: the observable attribute write keeps
the mutation alive without affecting the value stack or program namespace.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")

_INIT_OLD = '''    def __init__(self) -> None:
        self._synthetic_tracebacks: dict[int, "_PyTBProxy"] = {}
        self._current_frame: Frame | None = None
'''
_INIT_NEW = '''    def __init__(self) -> None:
        self._synthetic_tracebacks: dict[int, "_PyTBProxy"] = {}
        self._current_frame: Frame | None = None
        self._discarded: object = None
'''
_OLD = '''                elif op is Op.POP_TOP:
                    frame.stack.pop()
'''
_NEW = '''                elif op is Op.POP_TOP:
                    self._discarded = frame.stack.pop()
'''


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"native POP_TOP {label} normalization expected one match, found {count}"
        )
    return source.replace(old, new, 1)


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    source = _replace_once(source, _INIT_OLD, _INIT_NEW, "VM field")
    source = _replace_once(source, _OLD, _NEW, "handler")
    PATH.write_text(source, encoding="utf-8")

    if source.count("self._discarded = frame.stack.pop()") != 1:
        raise RuntimeError("native POP_TOP validation lost observable assigned pop")
    if source.count("self._discarded: object = None") != 1:
        raise RuntimeError("native POP_TOP validation lost discard field")
    if _OLD in source:
        raise RuntimeError("native POP_TOP bare pop remains after normalization")
    print("NORMALIZED NATIVE POP_TOP", 2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
