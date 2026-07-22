"""Repair native constructors whose parameter names collide with classes.

The pinned compiler may resolve a constructor parameter such as ``expr`` or
``pattern`` as the same-named global class token instead of the runtime
argument. Install an explicit ExprStmt initializer, rename every known
colliding parameter, and rewrite matching keyword call sites.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")
_EXPR_STMT = "_npr_ast_nodes_ExprStmt"
_PARAMETER_RENAMES: dict[str, dict[str, str]] = {
    _EXPR_STMT: {"expr": "expr_value"},
    "MatchAs": {"pattern": "pattern_value"},
    "match_case": {"pattern": "pattern_value"},
}


def _class(module: ast.Module, name: str) -> ast.ClassDef | None:
    classes = [
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == name
    ]
    if len(classes) > 1:
        raise RuntimeError(f"expected at most one class {name!r}, found {len(classes)}")
    return classes[0] if classes else None


def _expr_stmt_class(module: ast.Module) -> ast.ClassDef:
    class_node = _class(module, _EXPR_STMT)
    if class_node is None:
        raise RuntimeError("embedded native ExprStmt expected one class, found 0")
    return class_node


def _install_expr_stmt_initializer(class_node: ast.ClassDef) -> int:
    existing = [
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    ]
    if existing:
        raise RuntimeError(
            "embedded native ExprStmt unexpectedly already has an initializer"
        )

    initializer = ast.parse(
        "def __init__(self, expr_value: dict, pos: dict) -> None:\n"
        "    self.expr = expr_value\n"
        "    self.pos = pos\n"
    ).body[0]
    class_node.body.append(initializer)
    return 1


class _BoundNameRenamer(ast.NodeTransformer):
    def __init__(self, renames: dict[str, str]) -> None:
        self.renames = renames

    def visit_Name(self, node: ast.Name) -> ast.AST:
        replacement = self.renames.get(node.id)
        if replacement is not None:
            node.id = replacement
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        return node


class _KeywordCallRenamer(ast.NodeTransformer):
    def __init__(self) -> None:
        self.rewritten = 0

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if not isinstance(node.func, ast.Name):
            return node
        renames = _PARAMETER_RENAMES.get(node.func.id)
        if not renames:
            return node
        for keyword in node.keywords:
            replacement = renames.get(keyword.arg or "")
            if replacement is not None:
                keyword.arg = replacement
                self.rewritten += 1
        return node


def _rename_constructor_parameters(module: ast.Module) -> int:
    renamed = 0
    for class_name, requested in _PARAMETER_RENAMES.items():
        class_node = _class(module, class_name)
        if class_node is None:
            continue
        initializers = [
            node
            for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        ]
        if len(initializers) != 1:
            raise RuntimeError(
                f"class {class_name!r} expected one initializer, "
                f"found {len(initializers)}"
            )
        initializer = initializers[0]
        active: dict[str, str] = {}
        for argument in initializer.args.args[1:]:
            replacement = requested.get(argument.arg)
            if replacement is not None:
                active[argument.arg] = replacement
                argument.arg = replacement
                renamed += 1
        if not active:
            continue
        body_renamer = _BoundNameRenamer(active)
        initializer.body = [body_renamer.visit(statement) for statement in initializer.body]
    return renamed


def _is_self_field_assignment(
    node: ast.stmt,
    field: str,
    source_name: str,
) -> bool:
    return (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Attribute)
        and isinstance(node.targets[0].value, ast.Name)
        and node.targets[0].value.id == "self"
        and node.targets[0].attr == field
        and isinstance(node.value, ast.Name)
        and node.value.id == source_name
    )


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    installed = _install_expr_stmt_initializer(_expr_stmt_class(module))
    renamed = _rename_constructor_parameters(module)
    call_renamer = _KeywordCallRenamer()
    module = call_renamer.visit(module)

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    verified_class = _expr_stmt_class(verified)
    initializers = [
        node
        for node in verified_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    ]
    if len(initializers) != installed:
        raise RuntimeError("native ExprStmt initializer was not preserved uniquely")

    initializer = initializers[0]
    parameter_names = [argument.arg for argument in initializer.args.args]
    if parameter_names != ["self", "expr_value", "pos"]:
        raise RuntimeError(
            f"native ExprStmt initializer parameters changed: {parameter_names}"
        )
    expr_annotation = initializer.args.args[1].annotation
    pos_annotation = initializer.args.args[2].annotation
    if not (
        isinstance(expr_annotation, ast.Name)
        and expr_annotation.id == "dict"
        and isinstance(pos_annotation, ast.Name)
        and pos_annotation.id == "dict"
    ):
        raise RuntimeError("native ExprStmt initializer lost dict parameter types")
    if not any(
        _is_self_field_assignment(node, "expr", "expr_value")
        for node in initializer.body
    ):
        raise RuntimeError("native ExprStmt initializer does not copy expr value")
    if not any(
        _is_self_field_assignment(node, "pos", "pos")
        for node in initializer.body
    ):
        raise RuntimeError("native ExprStmt initializer does not copy pos")

    print(
        "REPAIRED NATIVE CONSTRUCTOR COLLISIONS",
        installed,
        renamed,
        call_renamer.rewritten,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
