"""Rename pattern-constructor parameters that collide with ``pattern``.

Run this after extended-semantics normalization has installed MatchAs defaults.
The pinned compiler otherwise stores the global ``pattern`` class token instead
of the constructor argument in MatchAs and match_case instances.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")
_RENAMES: dict[str, dict[str, str]] = {
    "MatchAs": {"pattern": "pattern_value"},
    "match_case": {"pattern": "pattern_value"},
}


def _classes(module: ast.Module) -> dict[str, ast.ClassDef]:
    result: dict[str, ast.ClassDef] = {}
    for node in module.body:
        if not isinstance(node, ast.ClassDef) or node.name not in _RENAMES:
            continue
        if node.name in result:
            raise RuntimeError(f"duplicate native pattern class: {node.name}")
        result[node.name] = node
    missing = [name for name in _RENAMES if name not in result]
    if missing:
        raise RuntimeError(
            "native pattern constructor class(es) missing: " + ", ".join(missing)
        )
    return result


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
        renames = _RENAMES.get(node.func.id)
        if renames is None:
            return node
        for keyword in node.keywords:
            replacement = renames.get(keyword.arg or "")
            if replacement is not None:
                keyword.arg = replacement
                self.rewritten += 1
        return node


def _rename_initializers(module: ast.Module) -> int:
    renamed = 0
    for class_name, class_node in _classes(module).items():
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
            replacement = _RENAMES[class_name].get(argument.arg)
            if replacement is not None:
                active[argument.arg] = replacement
                argument.arg = replacement
                renamed += 1
        if active != _RENAMES[class_name]:
            raise RuntimeError(
                f"class {class_name!r} collision parameters changed: {active}"
            )
        renamer = _BoundNameRenamer(active)
        initializer.body = [renamer.visit(statement) for statement in initializer.body]
    return renamed


def _verify(module: ast.Module) -> None:
    for class_name, class_node in _classes(module).items():
        initializer = next(
            node
            for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        )
        parameter_names = [argument.arg for argument in initializer.args.args]
        if "pattern" in parameter_names or "pattern_value" not in parameter_names:
            raise RuntimeError(
                f"class {class_name!r} pattern parameter was not repaired: "
                f"{parameter_names}"
            )
        assignments = [
            node
            for node in initializer.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Attribute)
            and isinstance(node.targets[0].value, ast.Name)
            and node.targets[0].value.id == "self"
            and node.targets[0].attr == "pattern"
        ]
        if not any(
            isinstance(node.value, ast.Name)
            and node.value.id == "pattern_value"
            for node in assignments
        ):
            raise RuntimeError(
                f"class {class_name!r} does not copy pattern_value"
            )


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    renamed = _rename_initializers(module)
    call_renamer = _KeywordCallRenamer()
    module = call_renamer.visit(module)
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")
    _verify(ast.parse(source))
    print(
        "REPAIRED NATIVE PATTERN CONSTRUCTOR COLLISIONS",
        renamed,
        call_renamer.rewritten,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
