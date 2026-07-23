"""Preserve parsed AST values and fast-path native expression statements.

The pinned compiler cannot safely compile the heterogeneous ``isinstance`` chain
that follows ``expr = self._parse_expr()`` in the embedded parser. It also lowers
a direct reference to that opaque local into the static dict type token ``0x7e``.
Box the returned node directly in a typed one-item list, fast-path newline-terminated
expression statements with a runtime ``box[0]`` load, then restore ``expr`` only
for the remaining assignment-target parsing. ``ExprStmt.expr`` is typed as ``dict``
to match the parser nodes' native dict-backed representation.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")
_EXPR_BOX_NAME = "__pyinbin_native_expr_values"


def _is_parse_expr_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
        and node.func.attr == "_parse_expr"
    )


def _is_expr_stmt_call(node: ast.expr | None) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_npr_ast_nodes_ExprStmt"
    )


def _is_box_subscript(node: ast.expr | None) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == _EXPR_BOX_NAME
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == 0
    )


def _is_newline_fast_path(node: ast.AST) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Call):
        return False
    function = node.test.func
    if not (
        isinstance(function, ast.Attribute)
        and isinstance(function.value, ast.Name)
        and function.value.id == "self"
        and function.attr == "_check"
        and len(node.test.args) == 1
        and isinstance(node.test.args[0], ast.Constant)
        and node.test.args[0].value == "NEWLINE"
    ):
        return False
    return any(
        isinstance(statement, ast.Return) and _is_expr_stmt_call(statement.value)
        for statement in node.body
    )


class _AnnotateRemainingExpressionResults(ast.NodeTransformer):
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


def _parser_class(module: ast.Module) -> ast.ClassDef:
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
    return parser_class


def _parse_stmt_method(module: ast.Module) -> ast.FunctionDef:
    parser_class = _parser_class(module)
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


def _normalize_expr_stmt_field(module: ast.Module) -> int:
    classes = [
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "_npr_ast_nodes_ExprStmt"
    ]
    if len(classes) != 1:
        raise RuntimeError(
            "embedded native ExprStmt class expected one definition, "
            f"found {len(classes)}"
        )
    fields = [
        node
        for node in classes[0].body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "expr"
    ]
    if len(fields) != 1:
        raise RuntimeError(
            "embedded native ExprStmt.expr expected one field, "
            f"found {len(fields)}"
        )
    fields[0].annotation = ast.copy_location(
        ast.Name(id="dict", ctx=ast.Load()),
        fields[0].annotation,
    )
    return 1


def _install_expression_statement_fast_path(method: ast.FunctionDef) -> int:
    replacement: list[ast.stmt] = []
    inserted = 0
    for statement in method.body:
        if not (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "expr"
            and _is_parse_expr_call(statement.value)
        ):
            replacement.append(statement)
            continue
        block = ast.parse(
            f"{_EXPR_BOX_NAME}: list[dict] = [self._parse_expr()]\n"
            "if self._check('NEWLINE'):\n"
            "    self._eat()\n"
            f"    return _npr_ast_nodes_ExprStmt({_EXPR_BOX_NAME}[0], pos)\n"
            f"expr: dict = {_EXPR_BOX_NAME}[0]\n"
        ).body
        replacement.extend(ast.copy_location(item, statement) for item in block)
        inserted += 1
    method.body = replacement
    return inserted


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    expr_stmt_field_count = _normalize_expr_stmt_field(module)
    method = _parse_stmt_method(module)
    fast_path_count = _install_expression_statement_fast_path(method)
    if fast_path_count != 1:
        raise RuntimeError(
            "native Parser._parse_stmt expression fast path expected one insertion, "
            f"found {fast_path_count}"
        )
    annotator = _AnnotateRemainingExpressionResults()
    annotator.visit(method)

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

    expr_stmt_class = next(
        node
        for node in verified.body
        if isinstance(node, ast.ClassDef) and node.name == "_npr_ast_nodes_ExprStmt"
    )
    expr_fields = [
        node
        for node in expr_stmt_class.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "expr"
        and isinstance(node.annotation, ast.Name)
        and node.annotation.id == "dict"
    ]
    if len(expr_fields) != expr_stmt_field_count:
        raise RuntimeError("native ExprStmt.expr dict annotation was not preserved")

    boxes = [
        node
        for node in verified_method.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == _EXPR_BOX_NAME
        and isinstance(node.value, ast.List)
        and len(node.value.elts) == 1
        and _is_parse_expr_call(node.value.elts[0])
    ]
    fast_paths = [node for node in verified_method.body if _is_newline_fast_path(node)]
    restored = [
        node
        for node in verified_method.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "expr"
        and _is_box_subscript(node.value)
    ]
    if len(boxes) != 1 or len(fast_paths) != 1 or len(restored) != 1:
        raise RuntimeError("native expression box sequence was not preserved uniquely")
    box_index = verified_method.body.index(boxes[0])
    fast_path_index = verified_method.body.index(fast_paths[0])
    restored_index = verified_method.body.index(restored[0])
    if (fast_path_index, restored_index) != (box_index + 1, box_index + 2):
        raise RuntimeError("native expression box sequence is not contiguous")

    fast_return = next(
        statement
        for statement in fast_paths[0].body
        if isinstance(statement, ast.Return) and _is_expr_stmt_call(statement.value)
    )
    assert isinstance(fast_return.value, ast.Call)
    if (
        fast_return.value.keywords
        or len(fast_return.value.args) != 2
        or not _is_box_subscript(fast_return.value.args[0])
    ):
        raise RuntimeError("native expression fast path does not load the boxed node")

    print("TYPED NATIVE EXPRSTMT FIELD", expr_stmt_field_count)
    print("BOXED NATIVE PARSER EXPRESSION RESULT", fast_path_count)
    print("TYPED REMAINING PARSER EXPRESSION RESULTS", annotator.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
