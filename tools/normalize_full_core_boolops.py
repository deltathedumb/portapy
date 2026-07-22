"""Force native BoolOp operands through dynamic attribute lookup.

The pinned asmpython compiler correctly narrows the vendored BoolOp enough to
read ``op``, but currently lowers the ``left`` and ``right`` fields to null
constants inside ``native_ast._convert_expr``.  Dynamic ``getattr`` uses the
object dictionary directly and preserves the existing short-circuit frontend
and VM implementation without rewriting user source or evaluating operands
more than once.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")


class _OperandRewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.in_convert = False
        self.in_boolop = False
        self.count = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        previous = self.in_convert
        self.in_convert = node.name == "_convert_expr"
        self.generic_visit(node)
        self.in_convert = previous
        return node

    def visit_If(self, node: ast.If) -> ast.AST:
        if not self.in_convert:
            return self.generic_visit(node)
        is_boolop = False
        test = node.test
        if (
            isinstance(test, ast.Call)
            and isinstance(test.func, ast.Name)
            and test.func.id == "isinstance"
            and len(test.args) == 2
        ):
            class_arg = test.args[1]
            if isinstance(class_arg, ast.Name) and class_arg.id.endswith("BoolOp"):
                is_boolop = True
            elif isinstance(class_arg, ast.Attribute) and class_arg.attr == "BoolOp":
                is_boolop = True
        previous = self.in_boolop
        self.in_boolop = is_boolop
        self.generic_visit(node)
        self.in_boolop = previous
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        node = self.generic_visit(node)
        if (
            self.in_boolop
            and isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "node"
            and node.attr in {"left", "right"}
            and isinstance(node.ctx, ast.Load)
        ):
            self.count += 1
            return ast.copy_location(
                ast.Call(
                    func=ast.Name(id="getattr", ctx=ast.Load()),
                    args=[
                        ast.Name(id="node", ctx=ast.Load()),
                        ast.Constant(node.attr),
                    ],
                    keywords=[],
                ),
                node,
            )
        return node


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    rewriter = _OperandRewrite()
    module = rewriter.visit(module)
    if rewriter.count != 2:
        raise RuntimeError(
            "native BoolOp operand normalization expected 2 fields, "
            f"found {rewriter.count}"
        )
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    reparsed = ast.parse(source)
    calls = [
        node
        for node in ast.walk(reparsed)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) == 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value in {"left", "right"}
    ]
    if len(calls) != 2:
        raise RuntimeError(
            f"native BoolOp dynamic operand validation found {len(calls)} calls"
        )
    print("NORMALIZED NATIVE BOOLOP OPERANDS", rewriter.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
