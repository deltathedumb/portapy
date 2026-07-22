"""Preserve native control-flow statement bodies through AST conversion.

``_convert_stmt`` accepts an opaque object. Direct accesses such as ``node.body``
can therefore lower as null/static type values in the pinned compiler even after
an ``isinstance`` check. Extract each body list with a typed ``getattr`` load and
hoist ``_convert_body`` before constructing the final AST statement.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")


def _convert_stmt(module: ast.Module) -> ast.FunctionDef:
    matches = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_convert_stmt"
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"native statement converter expected one _convert_stmt, found {len(matches)}"
        )
    return matches[0]


def _branch_type(test: ast.expr) -> str | None:
    if not (
        isinstance(test, ast.Call)
        and isinstance(test.func, ast.Name)
        and test.func.id == "isinstance"
        and len(test.args) == 2
        and isinstance(test.args[0], ast.Name)
        and test.args[0].id == "node"
        and isinstance(test.args[1], ast.Name)
    ):
        return None
    return test.args[1].id


def _safe_name(value: str) -> str:
    result = ""
    for character in value:
        if character.isalnum() or character == "_":
            result += character
        else:
            result += "_"
    return result.strip("_").lower()


class _BodyCallCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[tuple[ast.Call, str]] = []

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "_convert_body"
            and len(node.args) == 2
            and isinstance(node.args[0], ast.Attribute)
            and isinstance(node.args[0].value, ast.Name)
            and node.args[0].value.id == "node"
        ):
            self.calls.append((node, node.args[0].attr))
        self.generic_visit(node)


class _ReplaceBodyCalls(ast.NodeTransformer):
    def __init__(self, replacements: dict[int, str]) -> None:
        self.replacements = replacements
        self.changed = 0

    def visit_Call(self, node: ast.Call) -> ast.AST:
        replacement = self.replacements.get(id(node))
        if replacement is not None:
            self.changed += 1
            return ast.copy_location(
                ast.Name(id=replacement, ctx=ast.Load()),
                node,
            )
        return self.generic_visit(node)


def _normalize_function(function: ast.FunctionDef) -> int:
    changed = 0
    for branch in function.body:
        if not isinstance(branch, ast.If):
            continue
        type_name = _branch_type(branch.test)
        if type_name is None:
            continue
        collector = _BodyCallCollector()
        for statement in branch.body:
            collector.visit(statement)
        if not collector.calls:
            continue

        prefix = _safe_name(type_name.removeprefix("_npr_ast_nodes_"))
        fields: list[str] = []
        for _, field in collector.calls:
            if field not in fields:
                fields.append(field)

        declarations: list[ast.stmt] = []
        converted_names: dict[str, str] = {}
        for field in fields:
            raw_name = f"_native_{prefix}_{field}_body"
            converted_name = f"_native_converted_{prefix}_{field}_body"
            converted_names[field] = converted_name
            declarations.extend(
                ast.parse(
                    f'''{raw_name}: list[object] = getattr(node, {field!r})
{converted_name}: list[stmt] = _convert_body({raw_name}, lifted)
'''
                ).body
            )

        replacements = {
            id(call): converted_names[field]
            for call, field in collector.calls
        }
        rewriter = _ReplaceBodyCalls(replacements)
        original_body = [rewriter.visit(statement) for statement in branch.body]
        if rewriter.changed != len(collector.calls):
            raise RuntimeError(
                f"native {prefix} body call replacement expected {len(collector.calls)}, "
                f"found {rewriter.changed}"
            )
        branch.body = [*declarations, *original_body]
        changed += rewriter.changed
    return changed


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    function = _convert_stmt(module)
    changed = _normalize_function(function)
    if changed != 11:
        raise RuntimeError(
            "native statement body normalization missed shapes; "
            f"body_calls={changed}"
        )

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    verified_function = _convert_stmt(verified)
    unsafe = [
        node
        for node in ast.walk(verified_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_convert_body"
        and node.args
        and isinstance(node.args[0], ast.Attribute)
        and isinstance(node.args[0].value, ast.Name)
        and node.args[0].value.id == "node"
    ]
    typed_loads = [
        node
        for node in ast.walk(verified_function)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.annotation, ast.Subscript)
        and isinstance(node.annotation.value, ast.Name)
        and node.annotation.value.id == "list"
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "getattr"
    ]
    converted = [
        node
        for node in ast.walk(verified_function)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id.startswith("_native_converted_")
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_convert_body"
    ]
    nested_body_calls = [
        node
        for node in ast.walk(verified_function)
        if isinstance(node, ast.Call)
        and not (
            isinstance(getattr(node, "parent", None), ast.AnnAssign)
        )
        and isinstance(node.func, ast.Name)
        and node.func.id == "_convert_body"
    ]
    if unsafe or len(typed_loads) != 11 or len(converted) != 11:
        raise RuntimeError(
            "native statement body validation failed; "
            f"unsafe={len(unsafe)}, typed={len(typed_loads)}, converted={len(converted)}, "
            f"calls={len(nested_body_calls)}"
        )

    print("NORMALIZED NATIVE STATEMENT BODY LOADS", changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
