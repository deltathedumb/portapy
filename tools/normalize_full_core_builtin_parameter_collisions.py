"""Repair the compiler-special ``type`` parameter in native ExceptHandler.

Unlike ordinary names, the pinned backend lowers a parameter named ``type`` to
its builtin type token (-12). Rename the compatibility AST constructor
parameter while preserving the public ``self.type`` field and keyword calls.
"""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path("src/portapy")
_CLASS_NAME = "ExceptHandler"
_OLD = "type"
_NEW = "type_value"


class _BodyRenamer(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id == _OLD:
            node.id = _NEW
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
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            return node
        if name != _CLASS_NAME:
            return node
        for keyword in node.keywords:
            if keyword.arg == _OLD:
                keyword.arg = _NEW
                self.count += 1
        return node


def normalize_tree(root: Path) -> tuple[int, int, int]:
    paths = sorted(root.rglob("*.py"))
    trees = {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in paths
    }
    constructor_count = 0
    changed_paths: set[Path] = set()

    for path, tree in trees.items():
        for class_node in [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == _CLASS_NAME
        ]:
            initializers = [
                node
                for node in class_node.body
                if isinstance(node, ast.FunctionDef) and node.name == "__init__"
            ]
            if len(initializers) != 1:
                raise RuntimeError(
                    f"{path}: {_CLASS_NAME} expected one initializer, "
                    f"found {len(initializers)}"
                )
            initializer = initializers[0]
            matching = [
                argument
                for argument in [
                    *initializer.args.posonlyargs,
                    *initializer.args.args,
                    *initializer.args.kwonlyargs,
                ]
                if argument.arg == _OLD
            ]
            if len(matching) != 1:
                raise RuntimeError(
                    f"{path}: {_CLASS_NAME}.{_OLD} expected once, "
                    f"found {len(matching)}"
                )
            matching[0].arg = _NEW
            renamer = _BodyRenamer()
            initializer.body = [renamer.visit(statement) for statement in initializer.body]
            constructor_count += 1
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

    if constructor_count != 1:
        raise RuntimeError(
            f"native {_CLASS_NAME} constructor expected once, found {constructor_count}"
        )

    verified = {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in paths
    }
    for path, tree in verified.items():
        for class_node in [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == _CLASS_NAME
        ]:
            initializer = next(
                node
                for node in class_node.body
                if isinstance(node, ast.FunctionDef) and node.name == "__init__"
            )
            names = [argument.arg for argument in initializer.args.args]
            if _OLD in names or _NEW not in names:
                raise RuntimeError(
                    f"{path}: {_CLASS_NAME} builtin parameter repair was lost"
                )
            assignments = [
                statement
                for statement in initializer.body
                if isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Attribute)
                and isinstance(statement.targets[0].value, ast.Name)
                and statement.targets[0].value.id == "self"
                and statement.targets[0].attr == _OLD
            ]
            if not any(
                isinstance(statement.value, ast.Name)
                and statement.value.id == _NEW
                for statement in assignments
            ):
                raise RuntimeError(
                    f"{path}: {_CLASS_NAME} no longer copies {_NEW}"
                )

    return constructor_count, call_count, len(changed_paths)


def main() -> int:
    result = normalize_tree(ROOT)
    print("REPAIRED BUILTIN PARAMETER COLLISIONS", *result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
