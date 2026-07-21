"""Make frontend opcode maps compatible with the native string-key dictionary."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/frontend.py")


def replace(source: str, old: str, new: str, expected: int, label: str) -> str:
    count = source.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected}, found {count}")
    print("REPLACED", label, count)
    return source.replace(old, new)


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    keys = (
        "Add", "Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow",
        "BitAnd", "BitOr", "BitXor", "LShift", "RShift", "MatMult",
        "Eq", "Lt", "LtE", "Gt", "GtE", "NotEq", "Is", "IsNot",
        "In", "NotIn",
    )
    for key in keys:
        source = replace(
            source,
            f"    ast.{key}:",
            f'    "{key}":',
            1,
            f"string opcode key {key}",
        )
    source = replace(
        source,
        "type(node.op) in _BINARY_OPS",
        "type(node.op).__name__ in _BINARY_OPS",
        1,
        "binary opcode membership",
    )
    source = replace(
        source,
        "_BINARY_OPS[type(node.op)]",
        "_BINARY_OPS[type(node.op).__name__]",
        4,
        "binary opcode lookup",
    )
    source = replace(
        source,
        "all(type(op) in _COMPARE_OPS for op in node.ops)",
        "all(type(op).__name__ in _COMPARE_OPS for op in node.ops)",
        1,
        "compare opcode membership",
    )
    source = replace(
        source,
        "_COMPARE_OPS[type(op)]",
        "_COMPARE_OPS[type(op).__name__]",
        1,
        "compare opcode lookup",
    )
    source = replace(
        source,
        "type(node.op) not in _BINARY_OPS",
        "type(node.op).__name__ not in _BINARY_OPS",
        1,
        "augmented opcode membership",
    )
    PATH.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
