"""Preserve default-argument AST nodes through the standalone native bridge.

``A.FuncDef.defaults`` is an opaque external list to the pinned compiler. A bare
``node.defaults[index]`` receives the compiler's scalar fallback type, so a real
literal AST can collapse to a null pointer. The frontend then lowers
``_Lowerer.expr(None)`` while defining a function with defaults.

This pass runs after parser vendoring, so names and formatting may already have
changed. Rewrite ``_convert_arguments`` structurally and retain its vendored AST
argument constructor rather than relying on exact source text.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")


def _constructor_name(function: ast.FunctionDef) -> str:
    for node in ast.walk(function):
        if not isinstance(node, ast.ListComp):
            continue
        element = node.elt
        if (
            isinstance(element, ast.Call)
            and isinstance(element.func, ast.Name)
            and element.args
            and isinstance(element.args[0], ast.Name)
            and element.args[0].id == "name"
        ):
            return element.func.id
    raise RuntimeError("native default bridge lost its AST argument constructor")


def _is_normalized(function: ast.FunctionDef) -> bool:
    text = ast.unparse(function)
    return (
        'native_defaults: list[dict] = getattr(node, \'defaults\')' in text
        and "default_node: dict = native_defaults[index]" in text
        and "defaults.append(_convert_expr(default_node, lifted))" in text
    )


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    matches = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_convert_arguments"
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "native default argument bridge: expected one _convert_arguments, "
            f"found {len(matches)}"
        )
    function = matches[0]
    if _is_normalized(function):
        changed = 0
    else:
        constructor = _constructor_name(function)
        replacement = ast.parse(
            f'''all_args = [{constructor}(name) for name in node.params]
defaults: list[expr] = []
native_defaults: list[dict] = getattr(node, "defaults")
first_default = len(native_defaults)
index = 0
while index < len(native_defaults):
    default_node: dict = native_defaults[index]
    if default_node is not None:
        first_default = index
        break
    index += 1
if first_default < len(native_defaults):
    index = first_default
    while index < len(native_defaults):
        default_node: dict = native_defaults[index]
        defaults.append(_convert_expr(default_node, lifted))
        index += 1
return arguments([], all_args, None if node.vararg is None else {constructor}(node.vararg), [], [], None if node.kwarg is None else {constructor}(node.kwarg), defaults)
'''
        ).body
        function.body = replacement
        changed = 1

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    reparsed = ast.parse(source)
    functions = [
        node
        for node in reparsed.body
        if isinstance(node, ast.FunctionDef) and node.name == "_convert_arguments"
    ]
    if len(functions) != 1 or not _is_normalized(functions[0]):
        raise RuntimeError("native default argument structural validation failed")
    text = ast.unparse(functions[0])
    forbidden = (
        "first_default = len(node.defaults)",
        "_convert_expr(node.defaults[index], lifted)",
    )
    remaining = [marker for marker in forbidden if marker in text]
    if remaining:
        raise RuntimeError(f"unsafe native default extraction remains: {remaining}")
    print("NORMALIZED NATIVE DEFAULT ARGUMENT NODES", changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
