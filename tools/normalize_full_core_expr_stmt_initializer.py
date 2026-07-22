"""Install a compiler-safe initializer for the embedded native ExprStmt node.

The pinned compiler's synthesized dataclass initializer stores the static ``dict``
type token (0x7e) into ``ExprStmt.expr`` instead of the constructor argument. An
explicit initializer boxes both dict-backed parameters in a typed list and copies
runtime element loads into the instance fields, bypassing that synthesis bug.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")
_CLASS_NAME = "_npr_ast_nodes_ExprStmt"


def _expr_stmt_class(module: ast.Module) -> ast.ClassDef:
    classes = [
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == _CLASS_NAME
    ]
    if len(classes) != 1:
        raise RuntimeError(
            f"embedded native ExprStmt expected one class, found {len(classes)}"
        )
    return classes[0]


def _install_initializer(class_node: ast.ClassDef) -> int:
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
        "def __init__(self, expr: dict, pos: dict) -> None:\n"
        "    values: list[dict] = [expr, pos]\n"
        "    self.expr = values[0]\n"
        "    self.pos = values[1]\n"
    ).body[0]
    class_node.body.append(initializer)
    return 1


def _is_self_field_assignment(
    node: ast.stmt,
    field: str,
    index: int,
) -> bool:
    if not (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Attribute)
        and isinstance(node.targets[0].value, ast.Name)
        and node.targets[0].value.id == "self"
        and node.targets[0].attr == field
        and isinstance(node.value, ast.Subscript)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "values"
        and isinstance(node.value.slice, ast.Constant)
        and node.value.slice.value == index
    ):
        return False
    return True


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    class_node = _expr_stmt_class(module)
    installed = _install_initializer(class_node)

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
    if parameter_names != ["self", "expr", "pos"]:
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

    boxes = [
        node
        for node in initializer.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "values"
        and isinstance(node.value, ast.List)
        and len(node.value.elts) == 2
        and all(isinstance(value, ast.Name) for value in node.value.elts)
        and [value.id for value in node.value.elts] == ["expr", "pos"]
    ]
    if len(boxes) != 1:
        raise RuntimeError("native ExprStmt initializer parameter box is missing")
    if not any(
        _is_self_field_assignment(node, "expr", 0) for node in initializer.body
    ):
        raise RuntimeError("native ExprStmt initializer does not copy expr")
    if not any(
        _is_self_field_assignment(node, "pos", 1) for node in initializer.body
    ):
        raise RuntimeError("native ExprStmt initializer does not copy pos")

    print("INSTALLED NATIVE EXPRSTMT INITIALIZER", installed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
