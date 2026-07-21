"""Run the pinned asmpython CLI with probe-only compatibility rewrites.

The full-core transition reaches an asmpython f-string lowering path that can
synthesize an ``ascii`` reference even after the source has been normalized.
The pinned compiler does not expose ``ascii`` consistently across its
whole-program and semantic passes. This wrapper patches the exact
``driver.load_program`` binding used by compilation and rewrites synthesized
``ascii`` references to the already-supported ``repr`` builtin before sema.
"""
from __future__ import annotations

import dataclasses
import sys

from asmpython._backends import host_cli
from asmpython._compiler import ast_nodes as A
from asmpython._compiler import driver, program, sema


def _rewrite_ascii_references(node: object, counts: dict[str, int]) -> None:
    if isinstance(node, A.Call) and node.func == "ascii":
        node.func = "repr"
        counts["call"] += 1
    elif isinstance(node, A.Name) and node.name == "ascii":
        node.name = "repr"
        counts["name"] += 1

    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        for field in dataclasses.fields(node):
            _rewrite_ascii_references(getattr(node, field.name), counts)
    elif isinstance(node, dict):
        for key, value in node.items():
            _rewrite_ascii_references(key, counts)
            _rewrite_ascii_references(value, counts)
    elif isinstance(node, (list, tuple, set, frozenset)):
        for item in node:
            _rewrite_ascii_references(item, counts)


def main() -> int:
    sema.BUILTINS["ascii"] = (1, 1)
    if "ascii" not in program._ALWAYS_AVAILABLE:
        program._ALWAYS_AVAILABLE = frozenset(
            tuple(program._ALWAYS_AVAILABLE) + ("ascii",)
        )

    original_load_program = driver.load_program

    def load_program_with_probe_rewrites(*args: object, **kwargs: object):
        module = original_load_program(*args, **kwargs)
        counts = {"call": 0, "name": 0}
        _rewrite_ascii_references(module, counts)
        print("REWROTE ASCII CALLS", counts["call"])
        print("REWROTE ASCII NAMES", counts["name"])
        return module

    # driver._compile_program resolves this module-global binding directly.
    driver.load_program = load_program_with_probe_rewrites
    # Keep the source module aligned for any indirect callers.
    program.load_program = load_program_with_probe_rewrites

    try:
        return int(host_cli.main(sys.argv[1:]))
    finally:
        driver.load_program = original_load_program
        program.load_program = original_load_program


if __name__ == "__main__":
    raise SystemExit(main())
