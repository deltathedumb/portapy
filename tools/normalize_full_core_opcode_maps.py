"""Use native-safe opcode dispatch in the standalone full-core frontend."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/frontend.py")


def replace(source: str, old: str, new: str, expected: int, label: str) -> str:
    count = source.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected}, found {count}")
    print("REPLACED", label, count)
    return source.replace(old, new)


_HELPERS = '''def _binary_opcode(op: object) -> int | None:
    if isinstance(op, ast.Add):
        return Op.BINARY_ADD
    if isinstance(op, ast.Sub):
        return Op.BINARY_SUB
    if isinstance(op, ast.Mult):
        return Op.BINARY_MUL
    if isinstance(op, ast.Div):
        return Op.BINARY_DIV
    if isinstance(op, ast.FloorDiv):
        return Op.BINARY_FLOORDIV
    if isinstance(op, ast.Mod):
        return Op.BINARY_MOD
    if isinstance(op, ast.Pow):
        return Op.BINARY_POW
    if isinstance(op, ast.BitAnd):
        return Op.BINARY_BITAND
    if isinstance(op, ast.BitOr):
        return Op.BINARY_BITOR
    if isinstance(op, ast.BitXor):
        return Op.BINARY_BITXOR
    if isinstance(op, ast.LShift):
        return Op.BINARY_LSHIFT
    if isinstance(op, ast.RShift):
        return Op.BINARY_RSHIFT
    if isinstance(op, ast.MatMult):
        return Op.BINARY_MATMUL
    return None


def _compare_opcode(op: object) -> int | None:
    if isinstance(op, ast.Eq):
        return Op.COMPARE_EQ
    if isinstance(op, ast.Lt):
        return Op.COMPARE_LT
    if isinstance(op, ast.LtE):
        return Op.COMPARE_LE
    if isinstance(op, ast.Gt):
        return Op.COMPARE_GT
    if isinstance(op, ast.GtE):
        return Op.COMPARE_GE
    if isinstance(op, ast.NotEq):
        return Op.COMPARE_NE
    if isinstance(op, ast.Is):
        return Op.COMPARE_IS
    if isinstance(op, ast.IsNot):
        return Op.COMPARE_IS_NOT
    if isinstance(op, ast.In):
        return Op.COMPARE_IN
    if isinstance(op, ast.NotIn):
        return Op.COMPARE_NOT_IN
    return None
'''


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

    marker = "}\n\n\ndef _defer_annotation"
    if source.count(marker) != 1:
        raise RuntimeError(
            "opcode helper insertion point: expected 1, "
            f"found {source.count(marker)}"
        )
    source = source.replace(
        marker,
        "}\n\n\n" + _HELPERS + "\n\ndef _defer_annotation",
        1,
    )
    print("INSERTED NATIVE OPCODE HELPERS", 1)

    source = replace(
        source,
        "type(node.op) in _BINARY_OPS",
        "_binary_opcode(node.op) is not None",
        1,
        "binary opcode membership",
    )
    source = replace(
        source,
        "_BINARY_OPS[type(node.op)]",
        "_binary_opcode(node.op)",
        4,
        "binary opcode lookup",
    )
    source = replace(
        source,
        "all(type(op) in _COMPARE_OPS for op in node.ops)",
        "all(_compare_opcode(op) is not None for op in node.ops)",
        1,
        "compare opcode membership",
    )
    source = replace(
        source,
        "_COMPARE_OPS[type(op)]",
        "_compare_opcode(op)",
        1,
        "compare opcode lookup",
    )
    source = replace(
        source,
        "type(node.op) not in _BINARY_OPS",
        "_binary_opcode(node.op) is None",
        1,
        "augmented opcode membership",
    )
    PATH.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
