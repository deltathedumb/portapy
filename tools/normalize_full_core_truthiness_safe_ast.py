"""Finish typed truthiness without opaque AST-field dereferences."""
from __future__ import annotations

import ast
from pathlib import Path

from tools.normalize_full_core_truthiness_lists import main as normalize_truthiness


FRONTEND_PATH = Path("src/portapy/core/frontend.py")

_SAFE_KIND_METHOD = '''    def expression_kind(self, node: ast.expr) -> int:
        if isinstance(node, ast.Name):
            name: str = getattr(node, "id")
            return self.kind_hint(name)
        if isinstance(node, ast.Compare):
            return _TRUTH_BOOL
        if isinstance(node, ast.UnaryOp):
            operator = getattr(node, "op")
            if isinstance(operator, ast.Not):
                return _TRUTH_BOOL
        if isinstance(node, ast.JoinedStr):
            return _TRUTH_STRING
        if isinstance(node, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
            return _TRUTH_CONTAINER
        if isinstance(node, ast.Constant):
            value: object = getattr(node, "value")
            if value is None:
                return _TRUTH_NONE
            if value is True or value is False:
                return _TRUTH_BOOL
            if isinstance(value, str):
                return _TRUTH_STRING
            if isinstance(value, bytes):
                return _TRUTH_BYTES
            if isinstance(value, float):
                return _TRUTH_FLOAT
            if isinstance(value, int):
                return _TRUTH_INT
        return _TRUTH_UNKNOWN

'''


def _replace(source: str, old: str, new: str, label: str, expected: int = 1) -> str:
    count = source.count(old)
    if count != expected:
        raise RuntimeError(
            f"native AST-safe truthiness {label}: expected {expected}, found {count}"
        )
    return source.replace(old, new)


def main() -> int:
    normalize_truthiness()
    source = FRONTEND_PATH.read_text(encoding="utf-8")

    start = source.find("    def expression_kind(self, node: ast.expr) -> int:\n")
    end = source.find("    def emit_truth(self, node: ast.expr) -> None:\n", start)
    if start < 0 or end < 0:
        raise RuntimeError("native expression-kind method boundary was not found")
    source = source[:start] + _SAFE_KIND_METHOD + source[end:]

    source = _replace(
        source,
        "                self.set_kind_hint(node.targets[0].id, self.expression_kind(node.value))\n",
        "",
        "assignment walker removal",
    )
    source = _replace(
        source,
        "            self.emit_truth(node.operand)\n",
        "            self.emit_truth(getattr(node, \"operand\"))\n",
        "unary operand",
    )
    source = _replace(
        source,
        "            self.emit_truth(node.test)\n",
        "            self.emit_truth(getattr(node, \"test\"))\n",
        "assert test",
    )

    source = _replace(
        source,
        "                self.emit(Op.DUP_TOP)\n"
        "                exits.append(self.emit(Op.JUMP_IF_FALSE_KEEP if isinstance(node.op, ast.And) else Op.JUMP_IF_TRUE_KEEP))",
        "                self.emit(Op.DUP_TOP)\n"
        "                self.emit_truth(value)\n"
        "                exits.append(self.emit(Op.JUMP_IF_FALSE_KEEP if isinstance(node.op, ast.And) else Op.JUMP_IF_TRUE_KEEP))",
        "boolean operands",
    )
    source = _replace(
        source,
        "        elif isinstance(node, ast.IfExp):\n"
        "            self.expr(node.test)\n"
        "            otherwise = self.emit(Op.JUMP_IF_FALSE)",
        "        elif isinstance(node, ast.IfExp):\n"
        "            self.expr(node.test)\n"
        "            self.emit_truth(getattr(node, \"test\"))\n"
        "            otherwise = self.emit(Op.JUMP_IF_FALSE)",
        "conditional expression",
    )
    source = _replace(
        source,
        "        elif isinstance(node, ast.If):\n"
        "            self.expr(node.test)\n"
        "            otherwise = self.emit(Op.JUMP_IF_FALSE)",
        "        elif isinstance(node, ast.If):\n"
        "            self.expr(node.test)\n"
        "            self.emit_truth(getattr(node, \"test\"))\n"
        "            otherwise = self.emit(Op.JUMP_IF_FALSE)",
        "if statement",
    )
    source = _replace(
        source,
        "        elif isinstance(node, ast.While):\n"
        "            start = len(self.instructions)\n"
        "            self.expr(node.test)\n"
        "            exit_jump = self.emit(Op.JUMP_IF_FALSE)",
        "        elif isinstance(node, ast.While):\n"
        "            start = len(self.instructions)\n"
        "            self.expr(node.test)\n"
        "            self.emit_truth(getattr(node, \"test\"))\n"
        "            exit_jump = self.emit(Op.JUMP_IF_FALSE)",
        "while statement",
    )
    source = _replace(
        source,
        "                if case.guard is not None:\n"
        "                    self.expr(case.guard)\n"
        "                    guard_jump = self.emit(Op.JUMP_IF_FALSE)",
        "                if case.guard is not None:\n"
        "                    self.expr(case.guard)\n"
        "                    self.emit_truth(getattr(case, \"guard\"))\n"
        "                    guard_jump = self.emit(Op.JUMP_IF_FALSE)",
        "match guard",
    )

    FRONTEND_PATH.write_text(source, encoding="utf-8")
    forbidden = (
        "self.expression_kind(node.value)",
        "self.expression_kind(node.left)",
        "self.expression_kind(node.right)",
        "self.expression_kind(node.body)",
        "self.expression_kind(node.orelse)",
    )
    remaining = [marker for marker in forbidden if marker in source]
    if remaining:
        raise RuntimeError(
            "unsafe recursive AST kind inference survived: " + ", ".join(remaining)
        )
    if source.count("self.emit_truth(") < 7:
        raise RuntimeError("native truth conversion was not installed at all branch sites")
    print("NORMALIZED AST-SAFE NATIVE TRUTHINESS", source.count("self.emit_truth("))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
