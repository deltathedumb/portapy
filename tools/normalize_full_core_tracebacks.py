"""Disable host-style synthetic traceback publication in native builds."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")

_TABLE = '        self._synthetic_tracebacks: dict[int, "_PyTBProxy"] = {}\n'
_TRACEBACK_LOOKUP = (
    "self._synthetic_tracebacks.get(id(target), target.__traceback__)"
)
_TRACEBACK_BLOCK = '''                if isinstance(exc, BaseException) and not isinstance(exc, PyException):
                    tb_frame = _PyTBFrameProxy(frame.code, frame.globals, None)
                    prior = self._synthetic_tracebacks.get(id(exc))
                    self._synthetic_tracebacks[id(exc)] = _PyTBProxy(tb_frame, prior)
'''


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"native {label}: expected one source form, found {count}"
        )
    return source.replace(old, new, 1)


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    source = _replace_once(
        source,
        _TABLE,
        "",
        "traceback table annotation",
    )
    source = _replace_once(
        source,
        _TRACEBACK_LOOKUP,
        "None",
        "traceback attribute lookup",
    )
    source = _replace_once(
        source,
        _TRACEBACK_BLOCK,
        "",
        "traceback publication block",
    )
    if "_synthetic_tracebacks" in source:
        raise RuntimeError("native traceback normalization left stale storage references")
    PATH.write_text(source, encoding="utf-8")
    print("DISABLED NATIVE SYNTHETIC TRACEBACK PUBLICATION", 3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
