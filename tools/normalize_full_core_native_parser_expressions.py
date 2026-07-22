"""Preserve dict-backed AST expressions in the embedded native parser.

The pinned compiler defaults an unannotated result of ``self._parse_expr()`` to
an integer inside ``Parser._parse_stmt``. ``object`` annotations also fall back
to integer storage. Native class instances are dict-backed, and the following
``isinstance`` checks already dispatch through dict lookups, so annotate every
simple local assignment from ``_parse_expr`` in that method as ``dict``.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")


def _is_parse_expr_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
        and node.func.attr == "_parse_expr"
    )


class _AnnotateExpressionResults(ast.NodeTransformer):
    def __init__(self) -> None:
        self.count = 0

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
        self.generic_visit(node)
        if (
            len(node.targets) != 1
            or not isinstance(node.targets[0], ast.Name)
            or not _is_parse_expr_call(node.value)
        ):
            return node
        self.count += 1
        return ast.copy_location(
            ast.AnnAssign(
                target=node.targets[0],
                annotation=ast.Name(id="dict", ctx=ast.Load()),
                value=node.value,
                simple=1,
            ),
            node,
        )


def _parse_stmt_method(module: ast.Module) -> ast.FunctionDef:
    parser_class = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "_npr_parser_Parser"
        ),
        None,
    )
    if parser_class is None:
        raise RuntimeError("embedded native Parser class is missing")
    method = next(
        (
            node
            for node in parser_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "_parse_stmt"
        ),
        None,
    )
    if method is None:
        raise RuntimeError("embedded native Parser._parse_stmt is missing")
    return method


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    method = _parse_stmt_method(module)
    annotator = _AnnotateExpressionResults()
    annotator.visit(method)
    if annotator.count < 1:
        raise RuntimeError("native Parser._parse_stmt had no expression results to type")

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    verified_method = _parse_stmt_method(verified)
    remaining = [
        node
        for node in ast.walk(verified_method)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and _is_parse_expr_call(node.value)
    ]
    if remaining:
        raise RuntimeError(
            "native Parser._parse_stmt still contains untyped expression results"
        )
    typed = [
        node
        for node in ast.walk(verified_method)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.annotation, ast.Name)
        and node.annotation.id == "dict"
        and node.value is not None
        and _is_parse_expr_call(node.value)
    ]
    if len(typed) != annotator.count:
        raise RuntimeError("native parser expression annotations were not preserved")

    print("TYPED DICT-BACKED NATIVE PARSER EXPRESSIONS", annotator.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
