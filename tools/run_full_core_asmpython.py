"""Run the pinned asmpython CLI with probe-only compatibility builtins.

The full-core transition exercises Python syntax that can lower to ``ascii``
inside asmpython.  The pinned compiler recognizes ``repr`` but its semantic and
whole-program availability tables omit ``ascii``.  Run the CLI in this process
so both live tables are patched before the compiler imports and analyzes the
PortaPy program.
"""
from __future__ import annotations

import runpy
import sys

from asmpython._compiler import program, sema


def main() -> int:
    sema.BUILTINS["ascii"] = (1, 1)
    if "ascii" not in program._ALWAYS_AVAILABLE:
        program._ALWAYS_AVAILABLE = frozenset(
            tuple(program._ALWAYS_AVAILABLE) + ("ascii",)
        )
    if "ascii" not in sema.BUILTINS:
        raise RuntimeError("failed to enable ascii in asmpython semantic builtins")
    if "ascii" not in program._ALWAYS_AVAILABLE:
        raise RuntimeError("failed to enable ascii in whole-program builtins")

    sys.argv = ["asmpython", *sys.argv[1:]]
    runpy.run_module("asmpython", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
