"""Rename native locals that collide with flattened runtime class names.

The pinned compiler follows PortaPy's imports into one native symbol universe.
A function-local name such as ``keyword`` can therefore resolve to the imported
``keyword`` AST class instead of the loop item assigned at runtime. This final
source pass scans every PortaPy module, renames only non-parameter locals that
collide with any reachable class name, and verifies that none remain.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


ROOT = Path("src/portapy")
_PREFIX = "__portapy_local_"


@dataclass(frozen=True)
class _FunctionScope:
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
    depth: int


class _FunctionFinder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.depth = 0
        self.functions: list[_FunctionScope] = []

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
    ) -> None:
        self.functions.append(_FunctionScope(node, self.depth))
        self.depth += 1
        self.generic_visit(node)
        self.depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_function(node)


class _LocalCollector(ast.NodeVisitor):
    def __init__(
        self,
        root: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
    ) -> None:
        self.root = root
        self.bound: set[str] = set()
        self.global_names: set[str] = set()
        self.nonlocal_names: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bound.add(node.id)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.bound.add(node.name)
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocal_names.update(node.names)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.bound.add(alias.asname or alias.name.split(".", 1)[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.bound.add(alias.asname or alias.name)


class _LocalRenamer(ast.NodeTransformer):
    def __init__(self, renames: dict[str, str]) -> None:
        self.renames = renames

    def visit_Name(self, node: ast.Name) -> ast.AST:
        replacement = self.renames.get(node.id)
        if replacement is not None:
            node.id = replacement
        return node

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:
        if node.name in self.renames:
            node.name = self.renames[node.name]
        self.generic_visit(node)
        return node

    def visit_Import(self, node: ast.Import) -> ast.AST:
        for alias in node.names:
            bound = alias.asname or alias.name.split(".", 1)[0]
            replacement = self.renames.get(bound)
            if replacement is not None:
                alias.asname = replacement
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST:
        for alias in node.names:
            bound = alias.asname or alias.name
            replacement = self.renames.get(bound)
            if replacement is not None:
                alias.asname = replacement
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        return node


def _parameter_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
) -> set[str]:
    names = {
        argument.arg
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        )
    }
    if node.args.vararg is not None:
        names.add(node.args.vararg.arg)
    if node.args.kwarg is not None:
        names.add(node.args.kwarg.arg)
    return names


def _local_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
) -> set[str]:
    collector = _LocalCollector(node)
    collector.visit(node)
    return (
        collector.bound
        - _parameter_names(node)
        - collector.global_names
        - collector.nonlocal_names
    )


def _unique_name(name: str, occupied: set[str]) -> str:
    candidate = f"{_PREFIX}{name}"
    suffix = 2
    while candidate in occupied:
        candidate = f"{_PREFIX}{name}_{suffix}"
        suffix += 1
    occupied.add(candidate)
    return candidate


def _rename_tree(tree: ast.Module, class_names: set[str]) -> tuple[int, int]:
    finder = _FunctionFinder()
    finder.visit(tree)
    renamed_names = 0
    changed_functions = 0

    for scope in sorted(
        finder.functions,
        key=lambda item: (item.depth, getattr(item.node, "lineno", 0)),
        reverse=True,
    ):
        local_names = _local_names(scope.node)
        collisions = sorted(local_names & class_names)
        if not collisions:
            continue
        occupied = local_names | _parameter_names(scope.node) | class_names
        renames = {
            name: _unique_name(name, occupied)
            for name in collisions
        }
        renamer = _LocalRenamer(renames)
        if isinstance(scope.node, ast.Lambda):
            scope.node.body = renamer.visit(scope.node.body)
        else:
            scope.node.body = [renamer.visit(statement) for statement in scope.node.body]
        renamed_names += len(renames)
        changed_functions += 1

    return renamed_names, changed_functions


def _class_names(trees: dict[Path, ast.Module]) -> set[str]:
    return {
        node.name
        for tree in trees.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }


def _remaining_collisions(
    trees: dict[Path, ast.Module],
    class_names: set[str],
) -> list[str]:
    remaining: list[str] = []
    for path, tree in trees.items():
        finder = _FunctionFinder()
        finder.visit(tree)
        for scope in finder.functions:
            collisions = sorted(_local_names(scope.node) & class_names)
            if collisions:
                name = getattr(scope.node, "name", "<lambda>")
                remaining.append(
                    f"{path}:{getattr(scope.node, 'lineno', 0)}:{name}:"
                    + ",".join(collisions)
                )
    return remaining


def normalize_tree(root: Path) -> tuple[int, int, int]:
    paths = sorted(root.rglob("*.py"))
    trees = {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in paths
    }
    class_names = _class_names(trees)
    renamed_names = 0
    changed_functions = 0
    changed_files = 0

    for path, tree in trees.items():
        file_names, file_functions = _rename_tree(tree, class_names)
        if not file_names:
            continue
        ast.fix_missing_locations(tree)
        path.write_text(ast.unparse(tree) + "\n", encoding="utf-8")
        renamed_names += file_names
        changed_functions += file_functions
        changed_files += 1

    verified = {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in paths
    }
    remaining = _remaining_collisions(verified, class_names)
    if remaining:
        raise RuntimeError(
            "native local/class collisions remain: " + "; ".join(remaining)
        )
    return renamed_names, changed_functions, changed_files


def main() -> int:
    renamed_names, changed_functions, changed_files = normalize_tree(ROOT)
    if renamed_names < 1:
        raise RuntimeError("native local/class collision pass changed no names")
    print(
        "RENAMED NATIVE LOCAL CLASS COLLISIONS",
        renamed_names,
        changed_functions,
        changed_files,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
