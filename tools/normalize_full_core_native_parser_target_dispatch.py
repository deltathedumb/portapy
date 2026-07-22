"""Keep parsed expression nodes boxed through native target dispatch.

The pinned compiler lowers a ``dict``-annotated local holding an opaque AST node
as the static dict type token. The preceding one-item list subscript, however,
is a real runtime load. Remove the unsafe local and use that boxed load for every
remaining assignment-target check in ``Parser._parse_stmt``. Attribute targets
also need their ``obj`` and ``name`` fields loaded into typed runtime boxes before
constructing assignment nodes; direct opaque-field access otherwise becomes null.
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


def _is_attribute_target_test(statement: ast.If) -> bool:
    for node in ast.walk(statement.test):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "isinstance"
            and len(node.args) == 2
            and _is_box_subscript(node.args[0])
            and isinstance(node.args[1], ast.Name)
        ):
            continue
        type_name = node.args[1].id
        if type_name == "Attr" or type_name.endswith("_Attr"):
            return True
    return False


class _ReplaceAttributeTargetFields(ast.NodeTransformer):
    def __init__(self, suffix: int) -> None:
        self.suffix = suffix
        self.count = 0

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        if not _is_box_subscript(node.value) or node.attr not in {"obj", "name"}:
            return node
        self.count += 1
        box_name = f"_native_attr_{node.attr}_values_{self.suffix}"
        return ast.copy_location(
            ast.Subscript(
                value=ast.Name(id=box_name, ctx=ast.Load()),
                slice=ast.Constant(value=0),
                ctx=ast.Load(),
            ),
            node,
        )


def _normalize_attribute_target_fields(method: ast.FunctionDef) -> tuple[int, int]:
    branches = 0
    replacements = 0
    for statement in method.body:
        if not isinstance(statement, ast.If) or not _is_attribute_target_test(statement):
            continue

        rewriter = _ReplaceAttributeTargetFields(branches)
        rewritten_body = [rewriter.visit(item) for item in statement.body]
        if rewriter.count == 0:
            continue

        loads = ast.parse(
            f'''_native_attr_obj_values_{branches}: list[dict] = [getattr({_BOX_NAME}[0], "obj")]
_native_attr_name_values_{branches}: list[str] = [getattr({_BOX_NAME}[0], "name")]
'''
        ).body
        statement.body = [*loads, *rewritten_body]
        replacements += rewriter.count
        branches += 1

    return branches, replacements


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    method = _parse_stmt_method(module)
    removed, replacements = _rewrite_method(method)
    attr_branches, attr_fields = _normalize_attribute_target_fields(method)
    if (
        removed != 1
        or replacements < 4
        or attr_branches < 1
        or attr_fields < attr_branches * 2
    ):
        raise RuntimeError(
            "native parser target dispatch normalization missed shapes; "
            f"restores={removed}, expression_loads={replacements}, "
            f"attribute_branches={attr_branches}, attribute_fields={attr_fields}"
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
    stale_attr_fields = [
        node
        for node in ast.walk(verified_method)
        if isinstance(node, ast.Attribute)
        and _is_box_subscript(node.value)
        and node.attr in {"obj", "name"}
    ]
    typed_attr_boxes = [
        node
        for node in ast.walk(verified_method)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and (
            node.target.id.startswith("_native_attr_obj_values_")
            or node.target.id.startswith("_native_attr_name_values_")
        )
        and isinstance(node.value, ast.List)
        and len(node.value.elts) == 1
        and isinstance(node.value.elts[0], ast.Call)
        and isinstance(node.value.elts[0].func, ast.Name)
        and node.value.elts[0].func.id == "getattr"
    ]
    if (
        stale_restores
        or stale_loads
        or stale_attr_fields
        or len(boxed_loads) < replacements + 1
        or len(typed_attr_boxes) != attr_branches * 2
    ):
        raise RuntimeError(
            "native parser target dispatch validation failed; "
            f"restores={len(stale_restores)}, loads={len(stale_loads)}, "
            f"boxed={len(boxed_loads)}, stale_attr_fields={len(stale_attr_fields)}, "
            f"typed_attr_boxes={len(typed_attr_boxes)}"
        )

    print("KEPT NATIVE PARSER TARGET EXPRESSION BOXED", replacements)
    print("TYPED NATIVE ATTRIBUTE TARGET FIELDS", attr_fields)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
