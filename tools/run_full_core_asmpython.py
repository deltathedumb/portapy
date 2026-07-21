"""Run the pinned asmpython CLI with full-core compatibility extensions."""
from __future__ import annotations

import dataclasses
import sys

from asmpython._backends import host_cli
from asmpython._compiler import ast_nodes as A
from asmpython._compiler import codegen, driver, program, sema


def _source_position(node: object) -> str:
    pos = getattr(node, "pos", None)
    if pos is None:
        return "?:?"
    return f"{getattr(pos, 'line', '?')}:{getattr(pos, 'column', '?')}"


def _rewrite_ascii_references(
    node: object,
    counts: dict[str, int],
    path: str = "module",
) -> None:
    if isinstance(node, A.Call) and node.func == "ascii":
        print("ASCII CALL", path, _source_position(node))
        node.func = "repr"
        counts["call"] += 1
    elif isinstance(node, A.Name) and node.name == "ascii":
        print("ASCII NAME", path, _source_position(node), "TYPE", node.inferred_type)
        node.name = "repr"
        counts["name"] += 1

    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        for field in dataclasses.fields(node):
            _rewrite_ascii_references(
                getattr(node, field.name),
                counts,
                f"{path}.{type(node).__name__}.{field.name}",
            )
    elif isinstance(node, dict):
        for index, (key, value) in enumerate(node.items()):
            _rewrite_ascii_references(key, counts, f"{path}.dict[{index}].key")
            _rewrite_ascii_references(value, counts, f"{path}.dict[{index}].value")
    elif isinstance(node, (list, tuple, set, frozenset)):
        for index, item in enumerate(node):
            _rewrite_ascii_references(item, counts, f"{path}[{index}]")


def main() -> int:
    sema.BUILTINS["ascii"] = (1, 1)

    missing_exceptions = (
        "GeneratorExit",
        "ModuleNotFoundError",
        "StopAsyncIteration",
        "SyntaxError",
    )
    exceptions = frozenset(tuple(sema.BUILTIN_EXCEPTIONS) + missing_exceptions)
    sema.BUILTIN_EXCEPTIONS = exceptions
    codegen.BUILTIN_EXCEPTIONS = exceptions

    extra_types = (
        "object",
        "bytes",
        "bytearray",
        "frozenset",
        "type",
        "slice",
        "property",
        "classmethod",
        "staticmethod",
    )
    sema.BUILTIN_TYPE_NAMES = frozenset(
        tuple(sema.BUILTIN_TYPE_NAMES) + extra_types
    )
    next_type_id = min(codegen.BUILTIN_TYPE_IDS.values()) - 1
    for name in extra_types:
        if name not in codegen.BUILTIN_TYPE_IDS:
            codegen.BUILTIN_TYPE_IDS[name] = next_type_id
            next_type_id -= 1

    missing_available = tuple(
        name
        for name in missing_exceptions + extra_types
        if name not in program._ALWAYS_AVAILABLE
    )
    if missing_available:
        program._ALWAYS_AVAILABLE = frozenset(
            tuple(program._ALWAYS_AVAILABLE) + missing_available
        )
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

    driver.load_program = load_program_with_probe_rewrites
    program.load_program = load_program_with_probe_rewrites

    try:
        return int(host_cli.main(sys.argv[1:]))
    finally:
        driver.load_program = original_load_program
        program.load_program = original_load_program


if __name__ == "__main__":
    raise SystemExit(main())
