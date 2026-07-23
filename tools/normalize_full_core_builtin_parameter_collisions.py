"""Repair compiler-special native parameters that lower to builtin tokens.

The pinned backend treats selected parameter names as builtins even inside
constructors. ``ExceptHandler.type`` becomes token -12 and ``Subscript.slice``
becomes token -13 instead of loading their runtime arguments. Rename only these
verified cases while preserving their public instance fields and keyword calls.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


ROOT = Path("src/portapy")


@dataclass(frozen=True)
class _Repair:
    class_name: str
    field_name: str
    parameter_name: str


_REPAIRS = (
    _Repair("ExceptHandler", "type", "type_value"),
    _Repair("Subscript", "slice", "slice_value"),
)
_REPAIR_BY_CLASS = {repair.class_name: repair for repair in _REPAIRS}


class _BodyRenamer(ast.NodeTransformer):
    def __init__(self, old: str, new: str) -> None:
        self.old = old
        self.new = new

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id == self.old:
            node.id = self.new
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        return node


class _CallRenamer(ast.NodeTransformer):
    def __init__(self) -> None:
        self.count = 0

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.func, ast.Name):
            class_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            class_name = node.func.attr
        else:
            return node
        repair = _REPAIR_BY_CLASS.get(class_name)
        if repair is None:
            return node
        for keyword in node.keywords:
            if keyword.arg == repair.field_name:
                keyword.arg = repair.parameter_name
                self.count += 1
        return node


def _arguments(initializer: ast.FunctionDef) -> list[ast.arg]:
    return [
        *initializer.args.posonlyargs,
        *initializer.args.args,
        *initializer.args.kwonlyargs,
    ]


def _class_nodes(tree: ast.Module, class_name: str) -> list[ast.ClassDef]:
    return [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]


def normalize_tree(root: Path) -> tuple[int, int, int]:
    paths = sorted(root.rglob("*.py"))
    trees = {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in paths
    }
    constructor_count = 0
    changed_paths: set[Path] = set()
    seen: dict[_Repair, int] = {repair: 0 for repair in _REPAIRS}

    for path, tree in trees.items():
        for repair in _REPAIRS:
            for class_node in _class_nodes(tree, repair.class_name):
                initializers = [
                    node
                    for node in class_node.body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "__init__"
                ]
                if len(initializers) != 1:
                    raise RuntimeError(
                        f"{path}: {repair.class_name} expected one initializer, "
                        f"found {len(initializers)}"
                    )
                initializer = initializers[0]
                matching = [
                    argument
                    for argument in _arguments(initializer)
                    if argument.arg == repair.field_name
                ]
                if len(matching) != 1:
                    raise RuntimeError(
                        f"{path}: {repair.class_name}.{repair.field_name} "
                        f"expected once, found {len(matching)}"
                    )
                matching[0].arg = repair.parameter_name
                renamer = _BodyRenamer(
                    repair.field_name,
                    repair.parameter_name,
                )
                initializer.body = [
                    renamer.visit(statement)
                    for statement in initializer.body
                ]
                constructor_count += 1
                seen[repair] += 1
                changed_paths.add(path)

    call_count = 0
    for path, tree in trees.items():
        renamer = _CallRenamer()
        renamer.visit(tree)
        if renamer.count:
            changed_paths.add(path)
            call_count += renamer.count

    for path in changed_paths:
        ast.fix_missing_locations(trees[path])
        path.write_text(ast.unparse(trees[path]) + "\n", encoding="utf-8")

    wrong_counts = {
        f"{repair.class_name}.{repair.field_name}": count
        for repair, count in seen.items()
        if count != 1
    }
    if wrong_counts:
        raise RuntimeError(
            "native builtin parameter constructors expected once each: "
            f"{wrong_counts}"
        )

    verified = {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in paths
    }
    for path, tree in verified.items():
        for repair in _REPAIRS:
            for class_node in _class_nodes(tree, repair.class_name):
                initializer = next(
                    node
                    for node in class_node.body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "__init__"
                )
                names = [argument.arg for argument in _arguments(initializer)]
                if (
                    repair.field_name in names
                    or repair.parameter_name not in names
                ):
                    raise RuntimeError(
                        f"{path}: {repair.class_name} builtin parameter "
                        "repair was lost"
                    )
                assignments = [
                    statement
                    for statement in initializer.body
                    if isinstance(statement, ast.Assign)
                    and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Attribute)
                    and isinstance(statement.targets[0].value, ast.Name)
                    and statement.targets[0].value.id == "self"
                    and statement.targets[0].attr == repair.field_name
                ]
                if not any(
                    isinstance(statement.value, ast.Name)
                    and statement.value.id == repair.parameter_name
                    for statement in assignments
                ):
                    raise RuntimeError(
                        f"{path}: {repair.class_name} no longer copies "
                        f"{repair.parameter_name}"
                    )

    return constructor_count, call_count, len(changed_paths)


def main() -> int:
    result = normalize_tree(ROOT)
    print("REPAIRED BUILTIN PARAMETER COLLISIONS", *result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
