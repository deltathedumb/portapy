"""Load opaque native AST-node fields through the runtime object model.

The pinned compiler can fold ``node.field`` to a static field type token when
``node`` is annotated as ``object``. Native AST conversion then receives values
such as the dict type ID instead of the parsed child node. Rewrite every direct
field read in the conversion boundary to ``getattr(node, field)`` so the value is
loaded from the runtime instance dictionary.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")
_CONVERTERS = {
    "_convert_expr",
    "_convert_arguments",
    "_convert_func",
    "_convert_stmt",
}


class _NodeFieldLoader(ast.NodeTransformer):
    def __init__(self) -> None:
        self.count = 0
        self.fields: set[str] = set()

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        if not (
            isinstance(node.ctx, ast.Load)
            and isinstance(node.value, ast.Name)
            and node.value.id == "node"
            and not node.attr.startswith("__")
        ):
            return node
        self.count += 1
        self.fields.add(node.attr)
        return ast.copy_location(
            ast.Call(
                func=ast.Name(id="getattr", ctx=ast.Load()),
                args=[
                    ast.Name(id="node", ctx=ast.Load()),
                    ast.Constant(value=node.attr),
                ],
                keywords=[],
            ),
            node,
        )


def _converter_functions(module: ast.Module) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name in _CONVERTERS
    }


def _normalize_function(function: ast.FunctionDef) -> tuple[int, set[str]]:
    loader = _NodeFieldLoader()
    loader.visit(function)
    return loader.count, loader.fields


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    functions = _converter_functions(module)
    missing = sorted(_CONVERTERS - set(functions))
    if missing:
        raise RuntimeError(f"native AST field normalization missing converters: {missing}")

    total = 0
    fields: set[str] = set()
    counts: dict[str, int] = {}
    for name in sorted(functions):
        count, function_fields = _normalize_function(functions[name])
        counts[name] = count
        total += count
        fields.update(function_fields)

    if counts["_convert_expr"] == 0 or counts["_convert_stmt"] == 0:
        raise RuntimeError(
            "native AST field normalization found no opaque field loads; "
            f"counts={counts}"
        )

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    stale: list[tuple[str, str]] = []
    runtime_loads = 0
    for name, function in _converter_functions(verified).items():
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and isinstance(node.value, ast.Name)
                and node.value.id == "node"
                and not node.attr.startswith("__")
            ):
                stale.append((name, node.attr))
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "node"
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                runtime_loads += 1

    if stale or runtime_loads < total:
        raise RuntimeError(
            "native AST field validation failed; "
            f"stale={stale[:8]}, runtime_loads={runtime_loads}, expected={total}"
        )

    print(
        "NORMALIZED NATIVE AST RUNTIME FIELD LOADS",
        total,
        "FIELDS",
        len(fields),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
