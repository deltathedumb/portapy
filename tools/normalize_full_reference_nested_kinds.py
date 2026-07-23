"""Record source kind hints for assignments nested inside compound statements."""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")


def _is_indentation_guard(node: ast.If) -> bool:
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "indentation"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == 0
        and len(node.body) == 1
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Call)
        and isinstance(node.body[0].value.func, ast.Name)
        and node.body[0].value.func.id == "_native_record_statement_kind"
        and not node.orelse
    )


class _GuardRemover(ast.NodeTransformer):
    def __init__(self) -> None:
        self.count = 0

    def visit_If(self, node: ast.If) -> ast.AST:
        self.generic_visit(node)
        if not _is_indentation_guard(node):
            return node
        self.count += 1
        return ast.copy_location(node.body[0], node)


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    target = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_native_record_source_kinds"
        ),
        None,
    )
    if target is None:
        raise RuntimeError("native source-kind scanner is missing")
    remover = _GuardRemover()
    target = remover.visit(target)
    if remover.count != 1:
        raise RuntimeError(
            f"native nested-kind normalization expected one indentation guard, found {remover.count}"
        )
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    target_text = ast.unparse(
        next(
            node
            for node in verified.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_native_record_source_kinds"
        )
    )
    if "if indentation == 0" in target_text:
        raise RuntimeError("native nested-kind indentation guard survived")
    if target_text.count("_native_record_statement_kind(runtime, statement)") != 1:
        raise RuntimeError("native nested-kind recorder validation failed")
    print("NORMALIZED NATIVE NESTED VALUE KINDS", remover.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
