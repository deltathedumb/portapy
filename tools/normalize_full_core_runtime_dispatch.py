"""Remove host-introspection hazards from native VM iteration and imports.

``GET_ITER`` previously evaluated ``type(value).__name__`` before calling
``iter``. Native values are untagged pointers, so asking for the host type name
of a list can reinterpret the list header as a dictionary and crash. Iteration
needs no pre-conversion: Python's iterator protocol already handles lists,
dicts, and dictionary views.

Import handlers also used ``callable(loader)`` and direct ``loader(...)`` calls.
Native-compiled functions and VM callables are valid dispatcher targets even
when the host-style predicate rejects them, so check only for absence and route
calls through ``VirtualMachine._call``.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/vm.py")


def _is_attribute(node: ast.AST, owner: str, name: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == name
        and isinstance(node.value, ast.Name)
        and node.value.id == owner
    )


def _is_opcode_branch(node: ast.If, opcode: str) -> bool:
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "op"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Is)
        and len(test.comparators) == 1
        and _is_attribute(test.comparators[0], "Op", opcode)
    )


def _loader_presence_test() -> ast.Compare:
    return ast.Compare(
        left=ast.Name(id="loader", ctx=ast.Load()),
        ops=[ast.Is()],
        comparators=[ast.Constant(None)],
    )


class _ImportRewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.presence_checks = 0
        self.calls = 0

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if not isinstance(node.op, ast.Not) or not isinstance(node.operand, ast.Call):
            return node
        call = node.operand
        if (
            isinstance(call.func, ast.Name)
            and call.func.id == "callable"
            and len(call.args) == 1
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id == "loader"
        ):
            self.presence_checks += 1
            return ast.copy_location(_loader_presence_test(), node)
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if not (
            isinstance(node.func, ast.Name)
            and node.func.id == "loader"
            and len(node.args) == 1
            and not node.keywords
        ):
            return node
        self.calls += 1
        return ast.copy_location(
            ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="self", ctx=ast.Load()),
                    attr="_call",
                    ctx=ast.Load(),
                ),
                args=[
                    ast.Name(id="loader", ctx=ast.Load()),
                    ast.List(elts=[node.args[0]], ctx=ast.Load()),
                ],
                keywords=[],
            ),
            node,
        )


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.iteration = 0
        self.import_branches = 0
        self.presence_checks = 0
        self.loader_calls = 0

    def visit_If(self, node: ast.If) -> ast.AST:
        self.generic_visit(node)
        if _is_opcode_branch(node, "GET_ITER"):
            node.body = ast.parse(
                "value = frame.stack.pop()\n"
                "frame.stack.append(iter(value))\n"
            ).body
            self.iteration += 1
            return node
        if any(
            _is_opcode_branch(node, opcode)
            for opcode in ("IMPORT_NAME", "IMPORT_FROM", "IMPORT_ROOT", "IMPORT_RELATIVE_FROM")
        ):
            rewriter = _ImportRewrite()
            node.body = [rewriter.visit(statement) for statement in node.body]
            self.import_branches += 1
            self.presence_checks += rewriter.presence_checks
            self.loader_calls += rewriter.calls
        return node


def main() -> int:
    tree = ast.parse(PATH.read_text(encoding="utf-8"), filename=str(PATH))
    rewriter = _Rewrite()
    tree = rewriter.visit(tree)
    counts = (
        rewriter.iteration,
        rewriter.import_branches,
        rewriter.presence_checks,
        rewriter.loader_calls,
    )
    if rewriter.iteration != 1 or rewriter.import_branches != 4:
        raise RuntimeError(
            "native runtime dispatch expected one iterator and four import branches; "
            f"found {counts}"
        )
    if rewriter.presence_checks < 4 or rewriter.loader_calls < 8:
        raise RuntimeError(
            "native runtime import dispatch missed loader operations; "
            f"found {counts}"
        )

    ast.fix_missing_locations(tree)
    source = ast.unparse(tree) + "\n"
    PATH.write_text(source, encoding="utf-8")

    required = (
        "frame.stack.append(iter(value))",
        "loader is None",
        "self._call(loader, [imported])",
        "self._call(loader, [top_level])",
    )
    missing = [marker for marker in required if marker not in source]
    forbidden = (
        'type(value).__name__ in {',
        "callable(loader)",
    )
    remaining = [marker for marker in forbidden if marker in source]
    if missing or remaining:
        raise RuntimeError(
            f"native runtime dispatch validation failed: missing={missing}, remaining={remaining}"
        )

    print("NORMALIZED NATIVE RUNTIME DISPATCH", *counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
