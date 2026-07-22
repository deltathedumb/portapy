"""Keep parsed expression nodes boxed through native target dispatch.

The pinned compiler lowers a ``dict``-annotated local holding an opaque AST node
as the static dict type token. The preceding one-item list subscript, however,
is a real runtime load. Remove the unsafe local and use that boxed load for every
remaining assignment-target check in ``Parser._parse_stmt``.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")
_BOX_NAME = "__pyinbin_native_expr_values"


def _is_box_subscript(node: ast.expr | None) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == _BOX_NAME
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == 0
    )


def _box_subscript() -> ast.Subscript:
    return ast.Subscript(
        value=ast.Name(id=_BOX_NAME, ctx=ast.Load()),
        slice=ast.Constant(value=0),
        ctx=ast.Load(),
    )


def _parse_stmt_method(module: ast.Module) -> ast.FunctionDef:
    parser = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "_npr_parser_Parser"
        ),
        None,
    )
    if parser is None:
        raise RuntimeError("embedded native Parser class is missing")
    method = next(
        (
            node
            for node in parser.body
            if isinstance(node, ast.FunctionDef) and node.name == "_parse_stmt"
        ),
        None,
    )
    if method is None:
        raise RuntimeError("embedded native Parser._parse_stmt is missing")
    return method


class _ReplaceExpressionLoads(ast.NodeTransformer):
    def __init__(self) -> None:
        self.count = 0

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id != "expr" or not isinstance(node.ctx, ast.Load):
            return node
        self.count += 1
        return ast.copy_location(_box_subscript(), node)


def _rewrite_method(method: ast.FunctionDef) -> tuple[int, int]:
    body: list[ast.stmt] = []
    removed = 0
    replacements = 0
    after_restore = False

    for statement in method.body:
        is_restore = (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "expr"
            and _is_box_subscript(statement.value)
        )
        if is_restore:
            removed += 1
            after_restore = True
            continue
        if after_restore:
            rewriter = _ReplaceExpressionLoads()
            statement = rewriter.visit(statement)
            replacements += rewriter.count
        body.append(statement)

    method.body = body
    return removed, replacements


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    method = _parse_stmt_method(module)
    removed, replacements = _rewrite_method(method)
    if removed != 1 or replacements < 4:
        raise RuntimeError(
            "native parser target dispatch normalization missed shapes; "
            f"restores={removed}, expression_loads={replacements}"
        )

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    verified_method = _parse_stmt_method(verified)
    stale_restores = [
        node
        for node in ast.walk(verified_method)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "expr"
        and _is_box_subscript(node.value)
    ]
    stale_loads = [
        node
        for node in ast.walk(verified_method)
        if isinstance(node, ast.Name)
        and node.id == "expr"
        and isinstance(node.ctx, ast.Load)
    ]
    boxed_loads = [
        node
        for node in ast.walk(verified_method)
        if isinstance(node, ast.Subscript) and _is_box_subscript(node)
    ]
    if stale_restores or stale_loads or len(boxed_loads) < replacements + 1:
        raise RuntimeError(
            "native parser target dispatch validation failed; "
            f"restores={len(stale_restores)}, loads={len(stale_loads)}, "
            f"boxed={len(boxed_loads)}"
        )

    print("KEPT NATIVE PARSER TARGET EXPRESSION BOXED", replacements)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
