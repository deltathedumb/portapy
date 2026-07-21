"""Use native-safe string keys for synthetic traceback storage."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")

_REPLACEMENTS = (
    (
        '        self._synthetic_tracebacks: dict[int, "_PyTBProxy"] = {}',
        '        self._synthetic_tracebacks: dict[str, "_PyTBProxy"] = {}',
        "traceback table annotation",
    ),
    (
        "self._synthetic_tracebacks.get(id(target), target.__traceback__)",
        "self._synthetic_tracebacks.get(str(id(target)), target.__traceback__)",
        "traceback attribute lookup",
    ),
    (
        "prior = self._synthetic_tracebacks.get(id(exc))",
        "prior = self._synthetic_tracebacks.get(str(id(exc)))",
        "traceback prior lookup",
    ),
    (
        "self._synthetic_tracebacks[id(exc)] = _PyTBProxy(tb_frame, prior)",
        "self._synthetic_tracebacks[str(id(exc))] = _PyTBProxy(tb_frame, prior)",
        "traceback storage",
    ),
)


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    for old, new, label in _REPLACEMENTS:
        count = source.count(old)
        if count != 1:
            raise RuntimeError(
                f"native {label}: expected one source form, found {count}"
            )
        source = source.replace(old, new, 1)
    PATH.write_text(source, encoding="utf-8")
    print("NORMALIZED NATIVE TRACEBACK KEYS", len(_REPLACEMENTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
