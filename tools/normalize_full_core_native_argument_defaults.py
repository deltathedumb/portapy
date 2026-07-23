"""Preserve default-argument AST nodes through the standalone native bridge.

``A.FuncDef.defaults`` and the compatibility ``arguments.defaults`` field are
opaque to the pinned compiler when typed as the abstract ``expr`` base. Real
literal nodes can therefore collapse into a type token or null pointer before
``_Lowerer.expr`` receives them.

Run after parser vendoring, rewrite ``_convert_arguments`` structurally, box each
converted default as a dict-backed AST value, and change the compatibility
``arguments`` storage contract to ``list[dict]``.
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


def _arguments_initializer(module: ast.Module) -> ast.FunctionDef:
    classes = [
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "arguments"
    ]
    if len(classes) != 1:
        raise RuntimeError(
            "native default arguments class: expected one arguments class, "
            f"found {len(classes)}"
        )
    initializers = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    ]
    if len(initializers) != 1:
        raise RuntimeError(
            "native default arguments class: expected one initializer, "
            f"found {len(initializers)}"
        )
    return initializers[0]


def _list_annotation(item: ast.expr) -> ast.Subscript:
    return ast.Subscript(
        value=ast.Name(id="list", ctx=ast.Load()),
        slice=item,
        ctx=ast.Load(),
    )


def _dict_annotation() -> ast.Name:
    return ast.Name(id="dict", ctx=ast.Load())


def _optional_dict_annotation() -> ast.BinOp:
    return ast.BinOp(
        left=_dict_annotation(),
        op=ast.BitOr(),
        right=ast.Constant(value=None),
    )


def _normalize_arguments_storage(initializer: ast.FunctionDef) -> int:
    changed = 0
    for argument in initializer.args.args:
        if argument.arg == "defaults":
            expected = "list[dict]"
            if argument.annotation is None or ast.unparse(argument.annotation) != expected:
                argument.annotation = _list_annotation(_dict_annotation())
                changed += 1
        elif argument.arg == "kw_defaults":
            expected = "list[dict | None]"
            if argument.annotation is None or ast.unparse(argument.annotation) != expected:
                argument.annotation = _list_annotation(_optional_dict_annotation())
                changed += 1
    parameter_names = {argument.arg for argument in initializer.args.args}
    if "defaults" not in parameter_names or "kw_defaults" not in parameter_names:
        raise RuntimeError("native arguments initializer lost default fields")
    return changed


def _is_normalized(function: ast.FunctionDef) -> bool:
    text = ast.unparse(function)
    return (
        "defaults: list[dict] = []" in text
        and "native_defaults: list[dict] = getattr(node, 'defaults')" in text
        and "default_node: dict = native_defaults[index]" in text
        and "converted_default: dict = _convert_expr(default_node, lifted)" in text
        and "defaults.append(converted_default)" in text
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
    initializer = _arguments_initializer(module)
    storage_changes = _normalize_arguments_storage(initializer)

    if _is_normalized(function):
        bridge_changed = 0
    else:
        constructor = _constructor_name(function)
        replacement = ast.parse(
            f'''all_args = [{constructor}(name) for name in node.params]
defaults: list[dict] = []
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
        converted_default: dict = _convert_expr(default_node, lifted)
        defaults.append(converted_default)
        index += 1
return arguments([], all_args, None if node.vararg is None else {constructor}(node.vararg), [], [], None if node.kwarg is None else {constructor}(node.kwarg), defaults)
'''
        ).body
        function.body = replacement
        bridge_changed = 1

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
    verified_initializer = _arguments_initializer(reparsed)
    annotations = {
        argument.arg: ast.unparse(argument.annotation)
        for argument in verified_initializer.args.args
        if argument.annotation is not None
    }
    if annotations.get("defaults") != "list[dict]":
        raise RuntimeError("native positional default storage is not dict-backed")
    if annotations.get("kw_defaults") != "list[dict | None]":
        raise RuntimeError("native keyword default storage is not dict-backed")
    text = ast.unparse(functions[0])
    forbidden = (
        "first_default = len(node.defaults)",
        "_convert_expr(node.defaults[index], lifted)",
        "defaults: list[expr] = []",
        "defaults.append(_convert_expr(default_node, lifted))",
    )
    remaining = [marker for marker in forbidden if marker in text]
    if remaining:
        raise RuntimeError(f"unsafe native default extraction remains: {remaining}")
    print(
        "NORMALIZED NATIVE DEFAULT ARGUMENT NODES",
        bridge_changed,
        storage_changes,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
